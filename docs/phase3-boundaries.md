# Phase 3 boundaries

## Integration and credential resolution

`IntegrationManager` is the shared service used by direct execution and the
workflow compiler. It resolves connections by `(organization_id, integration)`
and returns only opaque credential references. `CredentialManager` owns
credential-reference ownership and revocation; raw secret values do not cross
the agent, planner, context, compiler, workflow, logging, or execution
payload boundaries.

The durable `IntegrationStateStore` persists connection metadata and
credential-reference metadata. It never persists raw credential values. A
durable store can be injected into `IntegrationManager`; implicit demo/test
contexts use an isolated in-memory store.

## OAuth status

Gmail and Slack are declared as OAuth2 integrations, but this repository does
not currently provide a user-facing authorization URL, state/callback flow,
authorization-code exchange, refresh-token handling, or revocation endpoint.
Phase 3 therefore uses explicitly supplied demo/test connection secrets through
the existing credential abstraction. This is not a production OAuth flow and
must not be treated as one.

## n8n boundary

Phase 4 adds the injectable `N8nClient` REST boundary and keeps
`N8nCredentialProvider` responsible for mapping Gnani references to IDs issued
by n8n. Raw secrets are accepted only by the explicit provisioning operation;
execution receives an n8n credential ID and never resolves raw secrets.
Workflow lifecycle, execution, status, health, and normalized n8n errors are
owned by the client. A native integration fallback remains available for the
demo path when n8n is unreachable, after the normal tenant and credential
checks have succeeded.

Agent AUTOMATE routing and full dynamic workflow orchestration remain Phase 5
work. The compiler infrastructure may resolve persisted integration references,
but the Agent does not route AUTOMATE plans through it in Phase 3.
