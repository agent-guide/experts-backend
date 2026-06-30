# User Library File Lifecycle (chat temporary files & promotion)

> Status: implemented (see §0 for the per-layer landing record). Originally a design proposal.
>
> This document proposes extending the existing user-library tables (`library_upload_sessions` and
> `library_files`) to carry **chat temporary files**, so a file attached in chat can later be
> **promoted** into a permanent library file without copying bytes and without new tables.
>
> Scope note: this is intentionally a library-only design. The upload handshakes stay separated by
> domain — knowledge-base documents keep their own handshake table (`document_upload_sessions`,
> already renamed from `upload_sessions`). No generic upload table and no `chat_turn_attachments`
> join table are introduced.

---

## 0. Implementation Status

Landing in dependency layers; each layer is one commit.

- [x] **Layer 1 — Schema migrations** (§3, §4, §9, §13): `library_files` lifecycle columns + named
      invariant check + existing-PostgreSQL `DO` block; `chat_session_id` on `library_upload_sessions`;
      `attachments` jsonb on `chat_turns`; lifecycle indexes. Verified on fresh SQLite (columns present,
      invariant enforced) and full test suite green.
- [x] **Layer 2 — Write-path invariants & routing guards** (§3.4, §4): app-layer
      `validate_lifecycle_invariant` re-validates every `library_files` write (covers existing
      SQLite where the DB check cannot be retrofitted); `create_file` / `create_upload_session`
      carry the lifecycle + `chat_session_id` columns; the library `complete-upload` rejects sessions
      bearing chat context (the chat-side symmetric guard lands with its endpoint in Layer 3);
      retention window is a config value (`chat_attachment_retention_seconds`, default 1 day).
- [x] **Layer 3 — Endpoints** (§7, §10, §11): `POST /chat/attachments/upload-url`,
      `POST /chat/attachments/complete-upload` (symmetric routing guard), `GET /chat/attachments?sessionId=`
      (temporary-only, session-scoped listing), `POST /library/files/{id}/promote` (conditional
      `expires_at > now()` SQL guard), and the `/library/files` repository-layer permanent-only filter.
      Chat endpoints delegate to `LibraryService` and reuse the chat session-ownership check. Covered by
      new end-to-end tests (lifecycle, save-to-library, both routing guards); 86 passed, ruff clean.
- [x] **Layer 4 — Turn integration & provenance** (§5, §7.3, §8, §9): `ChatTurnRequest`
      takes `attachmentFileIds`; the turn authorizes each id per §5, writes the self-contained
      `chat_turns.attachments` snapshot (§9), and delivers each attachment as a short-lived presigned
      URL (§8 option A) appended to the runtime input while `request_text` stays the bare question. A
      route pre-flight turns authorization failures into clean HTTP errors (not an empty 200 stream).
      Covered by tests (URL delivery + provenance, cross-session §5 denial); ruff clean.
- [x] **Layer 5 — Garbage collection** (§12): `LibraryService.purge_expired_temporary_files`
      hard-deletes expired temporary rows and removes their objects (§12.2 default), wired into the
      `/ops/storage/gc` pass as `purgedTemporaryFiles`. Session deletion stays TTL-only — `delete_session`
      does no attachment cleanup (§12.4). Covered by a GC test (expired file reclaimed, row dereferences
      to nothing) plus updated GC-endpoint assertions; 89 passed, ruff clean.

All five layers are implemented and tested. Delivery uses the §8 presigned-URL path (option A); the
§8.2 text-extraction form remains available as a no-network fallback but is not currently wired.

### 0.1 Redesign — unified upload + deferred (first-turn) binding

After the five layers landed, the upload/binding model was revised (the sections below reflect the
**current** design; the layer records above are the original history):

- **Upload is unified under `/library/files`.** A temporary file is uploaded via
  `POST /library/files/upload-url` + `/complete-upload` with `lifecycle: "temporary"` — there are **no**
  `/chat/attachments/*` routes. This lets a file be uploaded **before** a chat session exists, avoiding
  forced eager session creation.
- **A temporary file is created *unbound*** (`chat_session_id is null`) and **binds to a session
  exactly once, on the first turn that references it** (auto-bind). The invariant relaxes to
  `temporary ⇒ expires_at is not null` (session id is no longer required at creation).
- **Authorization (§5) gains an unbound case:** an unbound temporary file is readable by its owner
  (session-agnostic); once bound it is session-scoped; bound-to-another-session is rejected.
- **Listing is `GET /library/files?lifecycle=temporary[&sessionId=]`** (owner-scoped; all of the
  caller's temporary files without `sessionId`, a session's bound files with it). The default listing stays
  permanent-only. The `library_upload_sessions.chat_session_id` routing discriminator is retired
  (uploads no longer carry a session), and the two complete-upload routing guards are removed.

Everything else (provenance §9, delivery §8, promotion §10 which also works on unbound files, GC §12)
is unchanged.

---

## 1. Problem

Chat turns currently accept only `question` and `webSearchEnabled`; there is no file attachment
model. We want a user to:

- attach a file to a chat turn,
- reference that same file again in later turns of the same session,
- optionally keep the file permanently by saving it to their library,

without re-uploading, without copying bytes, and without leaking transient chat files into the
normal library view.

`library_files` is already the right catalog for user-owned files. It has `user_id`, `tenant_id`,
storage bucket/key, preview/download metadata, soft delete, and user-scoped read authorization. A
chat temporary file is just a user-owned file with a shorter life. So instead of inventing a new
attachment store, we add lifecycle metadata to `library_files` and reuse the existing library upload
handshake.

---

## 2. Goals

- Add chat temporary files by reusing `library_upload_sessions` and `library_files`.
- Distinguish temporary chat files from permanent library files via lifecycle metadata.
- Promote a temporary chat file into a permanent library file with no byte copy.
- Scope a temporary file to one chat session; require promotion for cross-session reuse.
- Keep object keys backend-generated; clients never submit object keys.
- Preserve soft-delete and garbage-collection behavior.
- Keep transient chat files out of the default library listing.

Non-goals:

- No generic upload table; document and library handshakes stay separate.
- No `chat_turn_attachments` join table (see §6 for why it is unnecessary).
- No change to knowledge-base / document ownership; documents remain platform-authored.
- Skills are unaffected.

---

## 3. `library_files` Lifecycle

### 3.1 New Columns

```sql
alter table library_files add column if not exists source text not null default 'library'
  check (source in ('library', 'chat_upload'));

alter table library_files add column if not exists lifecycle text not null default 'permanent'
  check (lifecycle in ('temporary', 'permanent'));

alter table library_files add column if not exists expires_at timestamptz;

alter table library_files add column if not exists promoted_at timestamptz;

alter table library_files add column if not exists chat_session_id text
  references chat_sessions(id) on delete set null;
```

- `chat_session_id` is the binding/authorization key for temporary files (see §5). It is **null while
  the file is unbound** (freshly uploaded, not yet used in a turn) and set **once** when the first turn
  references it (auto-bind, §7). Promotion leaves it as provenance but it no longer gates access.
- There is intentionally **no** `chat_turn_id` column. Upload happens before the turn request, and
  the turn id is not assigned until the ACP stream begins, so it cannot be filled at complete-upload.
  Per-turn provenance ("which turns referenced this file") belongs on the turn, via the
  `chat_turns.attachments` snapshot (§9), not on the file row.

### 3.2 Recommended Indexes

```sql
create index if not exists idx_library_files_temporary_expiry
  on library_files (lifecycle, expires_at)
  where deleted_at is null;

create index if not exists idx_library_files_chat_session
  on library_files (chat_session_id, created_at desc)
  where deleted_at is null;
```

### 3.3 Rules

- Normal library uploads: `source = 'library'`, `lifecycle = 'permanent'`.
- Chat temporary uploads: `source = 'chat_upload'`, `lifecycle = 'temporary'`,
  `chat_session_id = null` (**unbound** — set on first turn use, §7),
  `expires_at = now() + <retention window>` (default 1 day, configurable — §14.1).
- First-turn binding: `chat_session_id = <session>` via a once-only conditional update
  (`where chat_session_id is null`), so the bind is idempotent and race-safe (§7).
- Promotion: `lifecycle = 'permanent'`, `expires_at = null`, `promoted_at = now()`. The row keeps
  its bytes and object key; `chat_session_id` remains as provenance but no longer gates access.
- Deletion remains a soft delete via `deleted_at`.

### 3.4 Lifecycle Invariants (must be enforced, not just enumerated)

The per-column `check` enums above are necessary but not sufficient. Authorization (§5), promotion
(§10), and GC (§12) all assume stronger cross-column invariants; if dirty rows can exist, a temporary
file can end up with no expiry, or a permanent file can be mis-GC'd. Enforce:

- `lifecycle = 'temporary'` ⇒ `expires_at is not null` (a temporary file always has a deadline; the
  temporary-file GC pass and the promotion expiry guard both depend on this). Its `chat_session_id`
  may be null (unbound) — binding is deferred to first turn use (§7), so it is **not** part of the
  invariant.
- `lifecycle = 'permanent'` ⇒ `expires_at is null` (a permanent file is never a GC candidate; this is
  what promotion sets and what GC's `expires_at < now()` filter relies on).

Express this as a **table-level `check` in the canonical `create table library_files`**, e.g.:

```sql
check (
  (lifecycle = 'temporary' and expires_at is not null)
  or (lifecycle = 'permanent' and expires_at is null)
)
```

Landing this across all databases takes three coordinated places, because no single mechanism covers
them all:

- **Fresh databases (Postgres + SQLite):** the canonical `create table library_files` carries the
  `check`.
- **Existing PostgreSQL databases:** `create table if not exists` does not alter an existing table, so
  add the constraint with a PostgreSQL-only idempotent `DO` block (§13 step 5).
- **Existing SQLite databases:** the runner both skips bare `ADD CONSTRAINT` and strips the `DO`
  block, so the constraint cannot be retrofitted at the DB level there.

Because of that last gap, the **service/repository write paths must re-validate the same invariant**
in application code on every insert/update (complete-upload, promotion, GC). The DB `check` is the
backstop where it can exist; the app-layer check is what guarantees the invariant uniformly.

---

## 4. `library_upload_sessions` (minimal change)

The temporary-vs-permanent decision happens at **complete-upload** time, driven by the request's
`lifecycle` field (§7), so the handshake table is essentially unchanged. A nullable `chat_session_id`
column exists on the table:

```sql
alter table library_upload_sessions add column if not exists chat_session_id text
  references chat_sessions(id) on delete cascade;
```

> **Retired: the routing discriminator.** In the original design chat and library uploads used
> *separate* endpoints sharing this table, so `library_upload_sessions.chat_session_id` was a routing
> discriminator and each complete-upload endpoint rejected the other path's sessions. After the
> redesign (§0.1) upload is **unified** — a single `/library/files` upload with a `lifecycle` field —
> so uploads no longer carry a session, this column is **unused/vestigial**, and the two routing
> guards are removed. Binding to a session now happens on the *file* (`library_files.chat_session_id`)
> on first turn use (§7), not on the upload session.

Everything else (`file_type` check of `('image', 'file')`, size validation, status enum, existing
GC) is unchanged. A chat PDF resolves to `file_type = 'file'`. Note `library_files.chat_session_id`'s
`on delete set null` is likewise documentary — chat sessions are soft-deleted
(`ChatRepository.delete_session` sets `deleted_at`, never issues `DELETE`), so the FK action never
fires and cleanup on session deletion is TTL-based (§12.4).

### Object key scheme

Chat temporary files reuse the **existing library key scheme** rather than a separate `chat/` prefix:

```text
library/{tenant_id}/users/{user_id}/{file_id}/{safe_name}
```

This keeps all user-owned bytes under one prefix and makes promotion a true no-op on storage — no
object lives under a `chat/` prefix that would look wrong after promotion. Object-key paths are
organization hints, not permission boundaries; authorization is enforced by row fields, not by the
key.

---

## 5. Authorization and Scoping

The real security boundary is always `user_id` + `tenant_id` (every query carries both). On top of
that:

- **Temporary file, unbound** (`lifecycle = 'temporary'`, `chat_session_id is null`): readable by its
  owner (matching `user_id`/`tenant_id`) while not expired, **session-agnostic**. This is the
  freshly-uploaded, not-yet-used state.
- **Temporary file, bound** (`lifecycle = 'temporary'`, `chat_session_id = <session>`): readable by
  its owner while not expired **and** only when `chat_session_id` equals the current chat session.
  A bound file referenced from another session is rejected.
- **Permanent file** (`lifecycle = 'permanent'`): readable when `user_id` and `tenant_id` match;
  `chat_session_id` is ignored.

The unbound→bound transition happens once, automatically, on the first turn that references the file
(§7). Because all temporary files are owner-scoped, the session match is intra-user product isolation
(don't bleed one session's file into another), not a cross-user boundary.

---

## 6. Reuse Across Turns (why no join table)

Two behaviors fall out of the §5 rule automatically, so no `chat_turn_attachments` table is needed:

1. **Within-session reuse needs nothing extra.** The first turn binds the file to the session; later
   turns reference the same `file_id` and pass the §5 bound-to-this-session check. No copy, no extra
   row. The relationship "one file → many turns" does not need to be stored, because the file is found
   by id and authorized by `chat_session_id`.

2. **Cross-session reuse requires promotion.** A temporary file bound to session S1 fails the
   `chat_session_id` check in session S2, so the user must promote it to permanent first. After
   promotion it is an ordinary library file usable in any session. This constraint is not extra
   code — it is a side effect of the scoping check. (An *unbound* file, by contrast, binds to whatever
   session references it first; it is only "locked" to a session after that first use.)

---

## 7. Temporary File Flow (unified upload + first-turn binding)

Upload is unified under `/library/files` (no `/chat/attachments/*` routes). A temporary file is
uploaded **unbound** — before any chat session need exist — and binds to a session automatically on
the first turn that references it.

### 7.1 Upload URL

```text
POST /api/v1/library/files/upload-url
```

Request: `{ "fileName": "report.pdf", "mimeType": "application/pdf", "fileSizeBytes": 12345 }`.
Backend allocates a future `library_file_id` and a backend-owned object key under the library scheme
(§4) and returns `uploadSessionId`, `fileId`, `uploadUrl`, headers, object key, and expiry. This is
the ordinary library upload URL — the lifecycle is not decided until complete-upload.

### 7.2 Complete Upload

```text
POST /api/v1/library/files/complete-upload
```

Request:

```json
{
  "uploadSessionId": "upl_123",
  "lifecycle": "temporary"
}
```

Backend behavior:

1. Load the `library_upload_sessions` row; verify status, expiry, active tenant, owner user.
2. Stat the uploaded object and verify `file_size_bytes`.
3. Insert `library_files`:
   - `lifecycle = "temporary"` (default `"permanent"`): `source = 'chat_upload'`,
     `chat_session_id = null` (**unbound**), `expires_at = now() + <retention window>` (default 1 day,
     configurable — §14.1).
   - `lifecycle = "permanent"`: an ordinary library file (`source = 'library'`, `expires_at = null`).
4. Mark the upload session `completed`.

Response is a `LibraryFile` (carrying `lifecycle` and `expiresAt`).

### 7.3 Turn Request (authorize, auto-bind, deliver, record)

The chat turn request references completed file ids:

```json
{
  "question": "Summarize these files",
  "attachmentFileIds": ["file_123"]
}
```

Backend behavior, for each id:

1. Load `library_files` and apply the §5 rule. A permanent file passes on owner match. A temporary
   file must be owned and not expired; if **unbound**, it is **bound to this session now** via a
   once-only conditional update (`set chat_session_id = <session> where chat_session_id is null`),
   which is idempotent and race-safe; if already **bound to another session**, it is rejected.
2. Deliver the referenced files to the compute backend (§8).
3. Record them on the turn as a durable provenance snapshot (§9), mandatory-on-write.

A route pre-flight runs step 1 in *authorize-only* mode (allowing unbound files as-is, without
binding) **before** the SSE stream opens, so an unauthorized attachment is a clean HTTP error rather
than an empty 200 stream. The actual bind happens when the turn runs. A turn references completed
business resources (`library_files`) only — never upload sessions.

### 7.4 List Temporary Attachments

```text
GET /api/v1/library/files?lifecycle=temporary            # all temporary files owned by the caller
GET /api/v1/library/files?lifecycle=temporary&sessionId=thread_123   # a session's bound files
```

Owner-scoped and not-expired (§5/§11). Without `sessionId` it returns **all** the caller's temporary
files (both unbound "pending" uploads and ones already bound to a session); with `sessionId` it returns
only the files **bound** to that session (for re-referencing on reload). The default listing
(`GET /library/files`, no `lifecycle`) stays permanent-only.

---

## 8. Delivering Files to the ACP Runtime (compute)

**Delivery is content-only (committed).** Agents consume a file's *content*, never a file on disk, so
neither side ever stages bytes onto a filesystem. For each turn the backend mints short-lived
presigned download URLs for exactly the files the turn was §5-authorized to use and hands them to the
ACP runtime; the runtime **reads each URL's content directly into the model context** and does not
persist it. Because no bytes ever land on a filesystem — backend *or* runtime — there is no
shared-`cwd` exposure and no runtime filesystem isolation to arrange. Division of responsibility:

- **Backend** owns: authorization (§5), lifecycle (§3), the per-turn attachment snapshot (§9), and
  minting per-turn presigned URLs for the referenced files.
- **ACP runtime** owns: fetching each URL and feeding its content to the model, without writing the
  bytes to disk.

> **Out of scope: on-disk delivery.** No current agent needs the raw file as a path on disk (code
> execution, file-reading tools, local unpack/parse), so the design does not stage files into the
> agent's working directory. That matters because the ACP gateway's `cwd` is **tenant-level**
> (`AcpGatewayClient.prepare_cwd()` → `<cwd_base>/<tenant_id>`, `app/clients/acp_gateway.py`): writing
> attachment bytes there would expose them to every other session and user under the tenant, since the
> §5 `chat_session_id` rule gates only the *API* path, not a shared disk. Content-only delivery avoids
> that entirely by never touching a filesystem. If a future agent genuinely needs on-disk files, that
> is a **new design**: the runtime — not the backend — would have to stage into a session-scoped
> private directory (never the tenant `cwd`) and reclaim it at teardown. It is deliberately not part of
> this design.

### 8.1 Backend duties for presigned delivery

1. **Mint a presigned URL only for files that passed the §5 check for this turn** — never for the
   whole session, never for unauthorized ids.
2. **Re-mint per turn** (no single long-lived URL spanning the session). Re-minting naturally re-runs
   the §5 authorization each turn, so an expired/de-scoped file stops being deliverable.
3. **Use a short TTL bounded to the turn**, not the session.
4. **Treat the URL as a bearer capability.** Single-object scope plus short TTL bound the blast
   radius to one file for a few minutes; do not write the URL to logs or anywhere persisted.
5. **Ensure the runtime can actually reach the object-store endpoint** (internal vs public signing
   host must match the runtime's network position).

Promotion-safe: the object key is stable, so signing is identical before and after promotion, with
zero byte copy either way (§10).

**Shipped: presigned-URL delivery (option A).** `_prepare_attachments` mints one presigned GET URL
per authorized attachment (`attachment_delivery_url`, TTL `attachment_delivery_url_ttl_seconds`,
default 1h to outlive a turn) and appends a `[Attachment: name (mimeType)]\nContent available at:
<url>` block to the runtime `input`. `request_text` stays the bare question and the URL is never
persisted (excluded from the §9 snapshot). This works uniformly for every type — text, DOCX, image,
PDF — and shifts fetching to the engine.

> **Runtime prerequisites (option A).** The engine must (a) have a tool that fetches an external URL,
> (b) be able to reach the object-store signing host from its network position, and (c) fetch within
> the URL TTL. If any is unmet the block is inert text; the fallback is §8.2.

### 8.2 Text-extraction alternative (not currently wired)

When the runtime should not fetch at all, the backend may instead extract text server-side and inject
it into the turn input — no URL, no fetch, no filesystem. This is still content-only and needs no
runtime network access, but cannot deliver binary formats (images, PDF). It was the initial shipped
form and remains available as a fallback should the option-A prerequisites not hold.

Nothing is staged anywhere in either form, so there is no delivery copy for anyone to reclaim (§12.3).

---

## 9. Per-Turn Attachment Provenance

Within-session *reuse* is a runtime reference and needs nothing persisted to function. But durable
**provenance** — which files a given turn actually used — is not optional if history replay or audit
matters. `chat_turns` stores only `request_text`, so without a stored record the answer to "which
files produced this response?" is unrecoverable: a temporary file may have expired and been GC'd, and
the original request is not a reliable reconstruction source.

**Store a snapshot, not bare ids.** Recording only `attachment_file_ids` is not enough, because §12
hard-deletes a temporary file by default once it expires. Once the `library_files` row is gone, the id
dereferences to nothing — name, MIME type, size, the lifecycle it had *at use time*, and whether it
was later expired/deleted are all lost, so neither audit nor a history UI chip can be rendered. Store
a denormalized snapshot array on the turn instead, written at turn creation, rather than introducing
a join table:

```sql
-- Each element: {fileId, name, mimeType, sizeBytes, lifecycle, attachedAt}
alter table chat_turns add column if not exists attachments jsonb not null default '[]'::jsonb;
```

- **Write it at turn creation**, populated from the files the turn was authorized to use (after the
  §5 check), capturing each file's display metadata and its lifecycle *as of that turn*. The column
  has a default only so existing rows migrate cleanly; new turns that reference files always write it.
  Treating it as mandatory-on-write is what makes it a dependable provenance record rather than a
  best-effort hint.
- Because the snapshot is self-contained, it survives the referenced file being expired and hard-
  deleted by §12 GC — the chip still shows "report.pdf (expired)" with no live row to read. The
  `fileId` is retained so a still-live (e.g. promoted) file can still be re-opened, but replay no
  longer *depends* on the row existing.
- This keeps the data model flat (no `chat_turn_attachments` join table) while giving history replay
  and audit a durable source. The frontend renders chips from the snapshot directly instead of re-
  deriving them from the request or dereferencing ids.

**Scope boundary.** The snapshot answers exactly one question: *which files was this turn authorized
to reference* (the §5-checked set, for audit and history UI). It deliberately does **not** claim to
prove *which file contents the agent actually fed to the model* — that is the runtime's delivery
concern (§8). Keep the two apart: this column is backend-side authorized provenance and is independent
of how the runtime fetches and consumes the content.

---

## 10. Promotion Flow

```text
POST /api/v1/library/files/{file_id}/promote
```

Backend behavior:

1. Load the `library_files` row by `file_id`.
2. Verify `user_id`, `tenant_id`, `deleted_at is null`, `lifecycle = 'temporary'`, **and not
   expired** (`expires_at > now()`). A temporary file always has `expires_at` (§3.4 invariant), so
   there is no `expires_at is null` case to allow here.
3. Set:

```sql
update library_files
set lifecycle = 'permanent', expires_at = null, promoted_at = now(), updated_at = now()
where id = ?
  and user_id = ? and tenant_id = ?
  and deleted_at is null
  and lifecycle = 'temporary'
  and expires_at > now();
```

4. If the conditional update matches no row (expired, already permanent, or deleted), return a
   `409`-style error rather than promoting. Return the normal `LibraryFile` response on success.

The expiry check is enforced **in the SQL `where` clause**, not only in application code, so a
promotion racing the GC pass cannot resurrect an already-expired file. §5 forbids *reading* expired
temporary files; promotion must honor the same deadline, otherwise a user could revive an expired
file as permanent whenever GC has not yet run — silently defeating retention. (If product ever wants
an explicit "restore expired attachment" affordance, it should be a separate, deliberate action with
its own retention semantics, not a side effect of promote.)

Promotion does not check `chat_session_id`, so an **unbound** temporary file is promotable too — a
user can save a just-uploaded attachment to their library without ever using it in a turn.

No object copy is required: the file already lives under a backend-owned library object key.

---

## 11. User Visibility

Temporary files share the `library_files` table, so listings filter by `lifecycle`:

- **`/library/files` (default, no `lifecycle`) returns only `lifecycle = 'permanent'`,
  unconditionally.** A caller that does not ask for temporary files never sees them — the permanent
  default is applied **at the repository layer**.
- **`GET /library/files?lifecycle=temporary`** lists the caller's non-expired temporary files. Without
  `sessionId` it returns **all** of them (both unbound "pending" uploads and ones already bound to a
  session); with `&sessionId=<session>` it returns only files **bound** to that session. Both are
  owner-scoped.
- Chat turns continue to read individual temporary files by id under the §5 rule (auto-binding unbound
  ones on first use, §7.3).

**Why a `lifecycle` filter is safe here (superseding the original "separate route" rationale).** The
real security boundary is `user_id` + `tenant_id`, which `list_files` applies **unconditionally** on
every branch — so no lifecycle filter can cause a cross-user or cross-tenant leak. The session match
is *intra-user* product isolation, not a security boundary: the worst a forgotten `sessionId` could do
is show a user their own temporary files from another of their own sessions. Two safeguards remain: the
**default listing stays permanent-only** (temporary files never appear unless explicitly requested),
and temporary queries always add owner + tenant + not-expired. (The earlier design used a dedicated
`/chat/attachments` route to avoid a branch in the permanent-only filter; the redesign accepts the
branch because the owner/tenant boundary makes it safe, and unifies everything under `/library/files`.)

---

## 12. Garbage Collection

Existing library GC is unchanged; add one temporary-expiry pass.

### 12.1 Upload-session GC (existing)

Expire `library_upload_sessions` where `status = 'initiated'` and `expires_at < now`, remove their
objects.

### 12.2 Temporary-file GC (new)

1. Select `library_files where lifecycle = 'temporary' and expires_at < now and deleted_at is null`.
2. Hard-delete rows and remove objects (the default — §9's provenance snapshot already preserves
   history, so the row need not linger). Soft-delete remains a deliberate option only if product wants
   the row to persist for a reason beyond history rendering (§14.2).
3. Existing deleted-file GC later removes object bytes and hard-deletes rows.

Promotion clears `expires_at`, so promoted files are excluded from temporary-file GC.

### 12.3 No delivery copies to reclaim

Delivery is content-only (§8): the runtime reads attachment content straight from a presigned URL into
the model context and never writes it to disk, and the backend never stages bytes either. So there is
no on-disk delivery copy for anyone to garbage-collect. Object bytes have exactly one durable home —
the backend-owned library object key — and backend GC covers object storage and `library_files` rows
only.

### 12.4 Session deletion: TTL-only cleanup (decided)

Chat sessions are soft-deleted (§4), so the FK `on delete cascade` / `set null` declarations never
fire. The chosen policy (§14.1) is **TTL-only**: `ChatService.delete_session` does **no** eager
attachment cleanup. Deleting a session leaves its temporary attachments and pending upload sessions
live until their **own** TTL, where existing GC reclaims them:

- **Temporary attachments** expire on their own `expires_at` (1 day by default, §14.1) and are removed
  by the §12 temporary-file GC. Worst case, a deleted session's temporary bytes linger up to the
  retention window — accepted as the cost of the simpler policy.
- **Pending upload sessions** expire on their own `expires_at` and are removed by the existing
  upload-session GC (`LibraryRepository.list_expired_upload_sessions`), unchanged.
- **Promoted (permanent) files** are deliberately untouched — promotion severed the session scope (§5),
  so they are not session-scoped resources at all.

This is the **explicitly stated** acceptance the FK declarations require: they *imply* an immediate
cascade that does not happen, and we are choosing to let normal TTL handle it rather than reproducing
the cascade in `delete_session`. There is no delivery copy to clean up either — content-only delivery
stages nothing (§8, §12.3).

(The rejected alternative was eager cleanup in `delete_session`: bring each row's `expires_at` forward
to `now()` — *keeping* `status = 'initiated'` on upload sessions, since the GC selects only
`status = 'initiated' and expires_at < now`, so flipping to `'expired'` would strand the object. It
reclaims bytes sooner but adds write paths and a status-flip footgun; TTL-only was chosen for
simplicity.)

---

## 13. Migration Plan

Pure additive changes — no table merge, no data backfill:

1. Add the `library_files` lifecycle columns (§3.1) with idempotent `add column if not exists`.
   Existing rows default to `source = 'library'`, `lifecycle = 'permanent'`, which is correct.
2. Add `chat_session_id` to `library_upload_sessions` (§4).
3. Add the recommended indexes (§3.2).
4. Add the `attachments` snapshot column to `chat_turns` (§9). It stores a self-contained metadata
   snapshot per referenced file (not bare ids); the column carries a default for existing rows but is
   written on every new turn that references files, so provenance survives the file being expired and
   GC'd rather than being best-effort.
5. Land the §3.4 lifecycle invariant **on existing databases too**, not just fresh ones. A
   cross-column `check` placed only in the canonical `create table library_files` never reaches an
   already-created PostgreSQL table (`create table if not exists` is a no-op there), and the runner
   skips bare `ADD CONSTRAINT` under SQLite. Use a PostgreSQL-only idempotent `DO` block, which the
   runner's `_sqlite_compatible_sql` strips for SQLite (it removes any `do $$ ... $$;` block), so
   SQLite relies on the canonical `create table` check plus the app-layer re-validation (§3.4). The
   block **drops-then-adds** so the definition updates in place (the invariant was relaxed to allow
   unbound temporary files, §0.1):

   ```sql
   do $$
   begin
     alter table library_files drop constraint if exists library_files_lifecycle_invariant;
     alter table library_files add constraint library_files_lifecycle_invariant check (
       (lifecycle = 'temporary' and expires_at is not null)
       or (lifecycle = 'permanent' and expires_at is null)
     );
   end $$;
   ```

SQLite / dual-DB notes (the migration runner converts Postgres syntax for SQLite and treats schema
files as final definitions):

- Use one `add column if not exists` per `ALTER`; the runner checks column existence before
  applying.
- `ALTER COLUMN` / `ADD CONSTRAINT` / `DROP CONSTRAINT` are skipped under SQLite, so ship each new
  column's constraint inline on `ADD COLUMN` with a default. A multi-column `check` that cannot ride
  on a single `ADD COLUMN` goes in a PostgreSQL-only `do $$ ... $$;` block (stripped for SQLite) plus
  app-layer enforcement — see step 5.
- For dev rebuilds, the canonical SQL can be edited in place.
- Do not put semicolons inside SQL comments; keep `create table if not exists` in dependency order.

---

## 14. Decisions and Settled Defaults

Two groups. **§14.1** records the product decisions that were open and are now made. **§14.2** records
decisions the rest of this document already commits to. Nothing here is left open.

### 14.1 Product decisions (resolved)

- **Retention duration: 1 day by default, configurable.** A temporary chat file gets
  `expires_at = now() + 1 day` at complete-upload (§7.2); the window is a config value, not a
  hard-coded constant.
- **Session-deletion cleanup: TTL-only — no eager cleanup.** `ChatService.delete_session` does nothing
  to attachments; the session's temporary files and pending upload sessions live until their own TTL,
  where existing GC reclaims them (§12.4). This is the explicit acceptance the FK declarations require
  (the implied cascade does not fire and we let TTL handle it). Trade-off accepted: a deleted session's
  temporary bytes can linger up to the retention window.
- **Temporary files upload and list via `/library/files` (redesign §0.1).** Upload is
  `POST /library/files/complete-upload` with `lifecycle: "temporary"`; listing is
  `GET /library/files?lifecycle=temporary[&sessionId=]`. There are **no** `/chat/attachments/*` routes.
  The default listing stays permanent-only; temporary queries are owner + tenant + not-expired, so the
  `lifecycle` filter cannot leak across users (§11). *(This supersedes the earlier "dedicated chat
  route" decision.)*
- **Binding is deferred to first turn use.** A temporary file is uploaded unbound and bound to a
  session exactly once, automatically, on the first turn that references it (§7.3). This lets files be
  uploaded before a session exists, avoiding forced eager session creation.

### 14.2 Settled defaults (decided here; confirm where noted)

- **Delivery is content-only (§8).** Agents consume file content only, so the runtime reads each
  per-turn presigned URL straight into the model context (or the backend text-extracts server-side,
  §8.2) and nothing is ever written to a filesystem — backend or runtime. There is therefore no
  shared-`cwd` exposure and **no runtime isolation to confirm**: on-disk delivery is out of scope (§8),
  not a pending precondition. The presigned URL is per-turn, short-TTL, and §5-scoped (§8.1). If a
  future agent ever needs raw files on disk, that is a new design with its own runtime-isolation
  requirement — not an open item here. *(Shipped now: the §8 presigned-URL form, option A; the §8.2
  text-extraction form remains a no-network fallback.)*
- **Expired temporary files are hard-removed by default (§12).** §9's provenance snapshot already
  preserves history independently of the live row (a chip renders "report.pdf (expired)" with no row
  to read), so the original reason to *soft*-delete — keeping a row so history shows the attachment
  existed — is moot. Soft-delete remains available as a deliberate option if product later wants the
  row to linger for a reason other than history rendering, but it is not the default and should not be
  treated as an undecided fork.
