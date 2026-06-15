"""Smoke-test the agent-gateway ACP backend against a live gateway.

Drives the real AcpGatewayClient / AcpAdminClient (the same code the chat backend uses), so a
green run validates the actual integration, not a re-implementation. Connection config is read
from the environment / .env (EXPERT_NEXT_ACP_*) and can be overridden per flag.

Examples:
    # Run one turn against the data plane configured in .env
    python scripts/acp_smoke.py --input "Say hello in one short sentence."

    # Point at an ad-hoc gateway, run a turn, then a resume turn on the same session
    python scripts/acp_smoke.py --base-url http://localhost:8080 --prefix /acp --resume

    # Also exercise the admin plane (login -> list sessions -> transcript)
    python scripts/acp_smoke.py --transcript --list-sessions
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.clients.acp_admin import AcpAdminClient  # noqa: E402  (after sys.path bootstrap)
from app.clients.acp_gateway import AcpGatewayClient  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.errors import ApiError  # noqa: E402


class TurnResult:
    """Parsed outcome of one streamed turn."""

    def __init__(self) -> None:
        self.session_id: str | None = None
        self.text_parts: list[str] = []
        self.stop_reason: str | None = None
        self.error: str | None = None
        self.permissions: list[dict[str, Any]] = []

    @property
    def text(self) -> str:
        return "".join(self.text_parts)


def _settings_from_args(args: argparse.Namespace) -> Settings:
    # Only pass flags the caller actually set; pydantic-settings fills the rest from env / .env.
    overrides = {
        "acp_gateway_base_url": args.base_url,
        "acp_route_prefix": args.prefix,
        "acp_auth_token": args.token,
        "acp_default_model": args.model,
        "acp_default_cwd": args.cwd,
        "acp_admin_base_url": args.admin_base_url,
        "acp_admin_username": args.admin_user,
        "acp_admin_password": args.admin_password,
        "acp_service_id": args.service_id,
    }
    return Settings(**{k: v for k, v in overrides.items() if v is not None})


async def _run_turn(
    acp: AcpGatewayClient,
    *,
    thread_id: str,
    text: str,
    tenant_id: str | None,
    session_id: str | None,
    cwd: str | None,
    auto_permission: str | None,
) -> TurnResult:
    """Stream one turn, pretty-printing events as they arrive."""
    result = TurnResult()
    current_event: str | None = None
    data_line = ""
    pending_resolves: list[asyncio.Task] = []

    print(f"\n--- turn (thread_id={thread_id}, resume_session={session_id or '-'}) ---")
    async for line in acp.stream_turn(
        thread_id=thread_id,
        input=text,
        tenant_id=tenant_id,
        session_id=session_id,
        cwd=cwd,
    ):
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_line = line[len("data:") :].strip()
        elif line == "":
            if current_event:
                try:
                    data = json.loads(data_line) if data_line else {}
                except json.JSONDecodeError:
                    data = {}
                _handle_event(acp, result, current_event, data, tenant_id, auto_permission, pending_resolves)
            current_event = None
            data_line = ""

    if pending_resolves:
        await asyncio.gather(*pending_resolves, return_exceptions=True)

    print(f"\n[turn done] stop_reason={result.stop_reason!r} error={result.error!r} "
          f"chars={len(result.text)} session_id={result.session_id!r}")
    return result


def _handle_event(
    acp: AcpGatewayClient,
    result: TurnResult,
    event: str,
    data: dict[str, Any],
    tenant_id: str | None,
    auto_permission: str | None,
    pending_resolves: list[asyncio.Task],
) -> None:
    if event == "session":
        sid = str(data.get("session_id") or "").strip()
        if sid:
            result.session_id = sid
            print(f"[session] {sid}")
    elif event == "delta":
        text = data.get("text")
        if text:
            result.text_parts.append(str(text))
            print(str(text), end="", flush=True)
    elif event == "permission":
        result.permissions.append(data)
        request_id = data.get("request_id")
        print(f"\n[permission required] request_id={request_id} data={json.dumps(data.get('data'))[:300]}")
        if auto_permission and request_id:
            outcome = "cancelled" if auto_permission == "cancelled" else "selected"
            option_id = None if outcome == "cancelled" else auto_permission
            print(f"[permission] auto-resolving outcome={outcome} option_id={option_id}")
            pending_resolves.append(
                asyncio.create_task(
                    acp.resolve_permission(
                        request_id=str(request_id),
                        outcome=outcome,
                        option_id=option_id,
                        tenant_id=tenant_id,
                    )
                )
            )
    elif event == "done":
        result.stop_reason = data.get("stop_reason")
    elif event == "error":
        result.error = str(data.get("message") or "error")
        print(f"\n[error] {result.error}")
    else:
        # reasoning / tool_call / usage / ... — not part of the public chat contract, just surfaced.
        preview = data.get("text") or json.dumps(data.get("data"))[:200]
        print(f"\n[{event}] {preview}")


async def _run_admin(admin: AcpAdminClient, *, cwd: str | None, session_id: str | None, list_sessions: bool) -> None:
    print("\n=== admin plane ===")
    if list_sessions:
        sessions = await admin.list_sessions(cwd=cwd)
        items = (sessions or {}).get("sessions") or []
        print(f"[list_sessions] {len(items)} session(s) under cwd={cwd or '(service default)'}")
        for item in items[:10]:
            print(f"  - {item.get('session_id')} title={item.get('title')!r} updated_at={item.get('updated_at')}")
    if session_id:
        transcript = await admin.get_transcript(session_id=session_id, cwd=cwd)
        messages = (transcript or {}).get("messages") or []
        print(f"[transcript] session_id={session_id} {len(messages)} message(s)")
        for message in messages:
            text = str(message.get("text") or "")
            preview = text if len(text) <= 120 else text[:117] + "..."
            print(f"  [{message.get('role')}] {preview}")
    elif not list_sessions:
        print("(no session id captured from a turn; pass --list-sessions or run a turn first)")


async def _main(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    acp = AcpGatewayClient(settings)
    if not acp.base_url:
        print("ERROR: ACP gateway base URL is not configured (set --base-url or EXPERT_NEXT_ACP_GATEWAY_BASE_URL)")
        return 2

    thread_id = args.thread_id or f"thread_smoke_{uuid4().hex}"
    cwd = acp.prepare_cwd(args.tenant_id) if args.prepare_cwd else args.cwd

    print(f"gateway={acp.base_url} prefix={acp.route_prefix or '(none)'} thread_id={thread_id} cwd={cwd or '(service default)'}")

    try:
        result = await _run_turn(
            acp,
            thread_id=thread_id,
            text=args.input,
            tenant_id=args.tenant_id,
            session_id=None,
            cwd=cwd,
            auto_permission=args.auto_permission,
        )

        if args.resume:
            await _run_turn(
                acp,
                thread_id=thread_id,
                text=args.resume_input,
                tenant_id=args.tenant_id,
                session_id=result.session_id,
                cwd=cwd,
                auto_permission=args.auto_permission,
            )

        if args.transcript or args.list_sessions:
            admin = AcpAdminClient(settings)
            await _run_admin(admin, cwd=cwd, session_id=result.session_id, list_sessions=args.list_sessions)
    except ApiError as exc:
        print(f"\nERROR: {exc.code}: {exc.message} details={exc.details}")
        return 1

    print("\nOK")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the agent-gateway ACP backend.")
    parser.add_argument("--input", default="Say hello in one short sentence.", help="Turn prompt.")
    parser.add_argument("--thread-id", default=None, help="Caller-owned thread id (default: generated).")
    parser.add_argument("--tenant-id", default=None, help="X-Tenant-Id header (optional).")
    parser.add_argument("--resume", action="store_true", help="Run a second turn resuming the captured session.")
    parser.add_argument("--resume-input", default="And what did I just ask?", help="Prompt for the resume turn.")
    parser.add_argument("--transcript", action="store_true", help="Load the session transcript from the admin plane.")
    parser.add_argument("--list-sessions", action="store_true", help="List ACP sessions from the admin plane.")
    parser.add_argument(
        "--auto-permission",
        default=None,
        metavar="OUTCOME",
        help="Auto-answer permission prompts: 'cancelled' or an option id to select.",
    )
    parser.add_argument(
        "--prepare-cwd",
        action="store_true",
        help="Resolve+create the per-tenant cwd via the client (mirrors backend behavior).",
    )
    # Connection overrides (otherwise read from env / .env).
    parser.add_argument("--base-url", default=None, help="Override EXPERT_NEXT_ACP_GATEWAY_BASE_URL.")
    parser.add_argument("--prefix", default=None, help="Override EXPERT_NEXT_ACP_ROUTE_PREFIX.")
    parser.add_argument("--token", default=None, help="Override EXPERT_NEXT_ACP_AUTH_TOKEN.")
    parser.add_argument("--model", default=None, help="Override EXPERT_NEXT_ACP_DEFAULT_MODEL.")
    parser.add_argument("--cwd", default=None, help="Override EXPERT_NEXT_ACP_DEFAULT_CWD.")
    parser.add_argument("--admin-base-url", default=None, help="Override EXPERT_NEXT_ACP_ADMIN_BASE_URL.")
    parser.add_argument("--admin-user", default=None, help="Override EXPERT_NEXT_ACP_ADMIN_USERNAME.")
    parser.add_argument("--admin-password", default=None, help="Override EXPERT_NEXT_ACP_ADMIN_PASSWORD.")
    parser.add_argument("--service-id", default=None, help="Override EXPERT_NEXT_ACP_SERVICE_ID.")
    args = parser.parse_args()

    raise SystemExit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
