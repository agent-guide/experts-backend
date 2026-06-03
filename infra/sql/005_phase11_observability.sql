-- Phase 11: request ID traceability for async ingestion jobs.
-- source_request_id links each job back to the originating HTTP request,
-- enabling two-way lookup between API logs and worker logs.
alter table ingestion_jobs
  add column if not exists source_request_id text;
