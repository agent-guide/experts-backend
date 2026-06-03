-- T5: support knowledge-base document list sorted by created_at.
create index if not exists idx_documents_kb_created
  on documents (knowledge_base_id, created_at desc);
