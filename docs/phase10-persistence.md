# Phase 10 persistence and observability

## Backend boundary

The application-facing persistence boundary is the store object injected into
`IntegrationManager`:

```text
Agent / IntegrationManager
        -> persistence store interface
        -> IntegrationStateStore (SQLite compatibility/tests)
        -> PostgresStateStore (durable deployment)
```

`PostgresStateStore` requires an explicit DSN supplied by the deployment. The
application never reads `.env` to discover it. No package installation is
required: `psycopg2-binary` is already declared and available in the current
Python environment.

## PostgreSQL tables

The PostgreSQL implementation creates namespaced `gnani_*` tables so its
application-generated text IDs and canonical JSON do not conflict with the
legacy UUID-oriented bootstrap schema:

- `gnani_credential_references`
- `gnani_integration_connections`
- `gnani_automations`
- `gnani_conversations`
- `gnani_conversation_messages`
- `gnani_memory`
- `gnani_audit_events`
- `gnani_executions`

Organization-scoped lookups always include `organization_id` in the query.
Indexes cover organization ownership, timestamps, request IDs, and automation
ownership. All SQL values are passed as parameters.

## Security and migration

Only opaque credential references are persisted. Conversation content,
memory values, audit metadata, and execution metadata pass through the local
redaction helpers before storage. Raw secrets are never copied into the
PostgreSQL tables.

The existing SQLite database contains synthetic/demo state and remains the
compatibility backend for the current test suite. A production data migration
is intentionally not run automatically: it requires an explicitly selected
source and destination DSN plus an operational backup/verification plan. The
shared store methods preserve automation IDs, canonical workflows, n8n
workflow IDs, statuses, and timestamps when records are moved by a future
explicit migration utility.

## Observability

Agent requests and validated plans emit sanitized audit events keyed by the
existing `run_id` as both request and run correlation identifiers. Durable
conversation, memory, audit-event, and execution APIs are available on both
stores for the next integration step without exposing raw plans or secrets.
