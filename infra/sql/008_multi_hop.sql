alter table chat_tasks
  add column if not exists multi_hop_config jsonb;

alter table chat_task_events
  drop constraint if exists chat_task_events_event_type_check;

alter table chat_task_events
  add constraint chat_task_events_event_type_check
  check (event_type in (
    'queued', 'picked', 'retrieval', 'stop', 'error', 'cancel_requested', 'cancelled',
    'multi_hop_start', 'multi_hop_complete', 'multi_hop_fallback'
  ));
