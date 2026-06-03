-- T4: support efficient polling of ingestion jobs by document
create index if not exists idx_ingestion_jobs_document_created
  on ingestion_jobs (document_id, created_at desc);

-- T5: support knowledge-base document list sorted by created_at
create index if not exists idx_documents_kb_created
  on documents (knowledge_base_id, created_at desc);
