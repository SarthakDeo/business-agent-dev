import requests
import pytest

from backend.agent.context_manager import ConversationContext
from backend.agent.execution_manager import ExecutionError, execute_plan
from backend.integrations import (
    IntegrationManager,
    N8nClient,
    N8nConfig,
    N8nCredentialError,
    N8nCredentialProvider,
    N8nError,
)


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def client_with(*responses):
    session = FakeSession(responses)
    return N8nClient(N8nConfig("http://n8n.test", "fake-api-key"), session), session


def test_client_health_and_workflow_lifecycle():
    client, session = client_with(
        FakeResponse(data={"status": "ok"}),
        FakeResponse(data={"id": "wf-1"}),
        FakeResponse(data={"id": "wf-1", "name": "demo"}),
        FakeResponse(data={"id": "wf-1", "name": "updated"}),
        FakeResponse(data={"id": "wf-1", "active": True}),
        FakeResponse(data={"id": "wf-1", "active": False}),
        FakeResponse(status_code=204),
    )

    assert client.health_check()["status"] == "ok"
    assert client.create_workflow({"name": "demo"})["id"] == "wf-1"
    assert client.get_workflow("wf-1")["name"] == "demo"
    assert client.update_workflow("wf-1", {"name": "updated"})["name"] == "updated"
    assert client.activate_workflow("wf-1")["active"] is True
    assert client.deactivate_workflow("wf-1")["active"] is False
    assert client.delete_workflow("wf-1") == {}
    assert [call[0] for call in session.calls] == ["GET", "POST", "GET", "PUT", "POST", "POST", "DELETE"]

    # Health check lives at the root path (not under /api/v1)
    assert session.calls[0][1] == "http://n8n.test/healthz"
    # All REST data-plane calls must go through /api/v1
    for method_index, expected_fragment in [
        (1, "/api/v1/workflows"),          # create_workflow
        (2, "/api/v1/workflows/wf-1"),     # get_workflow
        (3, "/api/v1/workflows/wf-1"),     # update_workflow
        (4, "/api/v1/workflows/wf-1"),     # activate_workflow
        (5, "/api/v1/workflows/wf-1"),     # deactivate_workflow
        (6, "/api/v1/workflows/wf-1"),     # delete_workflow
    ]:
        assert expected_fragment in session.calls[method_index][1], (
            f"Call {method_index} URL {session.calls[method_index][1]!r} does not contain {expected_fragment!r}"
        )


def test_rest_paths_use_api_v1_prefix():
    """Every REST method must route through /api/v1; webhooks must NOT."""
    client, session = client_with(
        FakeResponse(data={"executionId": "exec-1", "data": {}}),  # execute_workflow
        FakeResponse(data={"id": "exec-1", "status": "success", "data": {}}),  # get_execution
        FakeResponse(data={"id": "n8n-cred-1"}),  # create_credential
        FakeResponse(data={"result": "ok"}),  # invoke_webhook
    )

    client.execute_workflow("wf-1", {})
    client.get_execution("exec-1")
    client.create_credential("gnani-crm", "gnani-org-crm", {"value": "s"})
    client.invoke_webhook("wf-1", {})

    urls = [call[1] for call in session.calls]
    assert "/api/v1/workflows/wf-1/run" in urls[0]
    assert "/api/v1/executions/exec-1" in urls[1]
    assert "/api/v1/credentials" in urls[2]
    # Webhook must NOT go through /api/v1
    assert "/webhook/wf-1" in urls[3]
    assert "/api/v1/webhook" not in urls[3]


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (FakeResponse(status_code=401, data={}), "AUTHENTICATION_FAILED"),
        (FakeResponse(status_code=404, data={}), "NOT_FOUND"),
        (FakeResponse(status_code=500, data={}), "N8N_REQUEST_FAILED"),
        (FakeResponse(data=ValueError()), "MALFORMED_RESPONSE"),
    ],
)
def test_client_normalizes_failures_without_response_body(response, code):
    client, _ = client_with(response)
    with pytest.raises(N8nError) as error:
        client.get_workflow("wf-1")
    assert error.value.code == code
    assert "fake-api-key" not in str(error.value)


def test_client_normalizes_connection_and_execution_failures():
    client, _ = client_with(requests.ConnectionError("secret-api-key"))
    with pytest.raises(N8nError, match="unreachable") as error:
        client.health_check()
    assert error.value.code == "CONNECTION_FAILED"
    assert "secret-api-key" not in str(error.value)

    client, _ = client_with(FakeResponse(status_code=500, data={}))
    with pytest.raises(N8nError) as error:
        client.execute_workflow("wf-1", {})
    assert error.value.code == "EXECUTION_FAILED"


def test_client_normalizes_execution_and_status():
    client, _ = client_with(
        FakeResponse(data={"executionId": "exec-1", "data": {"items": [1]}}),
        FakeResponse(data={"id": "exec-1", "status": "success", "data": {"items": [1]}}),
    )
    assert client.execute_workflow("wf-1", {}) == {
        "status": "queued", "execution_id": "exec-1", "result": {"items": [1]}
    }
    assert client.get_execution("exec-1")["status"] == "success"


def test_provider_provisions_only_with_n8n_issued_id_and_hides_secret():
    client, session = client_with(FakeResponse(data={"id": "n8n-cred-1"}))
    provider = N8nCredentialProvider()
    reference = provider.provision("org-a", "slack", "FAKE_SECRET", client=client)

    assert reference.id == "n8n-cred-1"
    assert "FAKE_SECRET" not in str(reference)
    request_payload = session.calls[0][2]["json"]
    assert request_payload["data"]["value"] == "FAKE_SECRET"


def test_provider_rejects_wrong_tenant_and_unmapped_reference():
    provider = N8nCredentialProvider()
    provider.register_mapping("org-a", "cred-1", "n8n-cred-1", "slack")
    with pytest.raises(N8nCredentialError):
        provider.resolve_reference("org-b", "cred-1")
    with pytest.raises(N8nCredentialError):
        provider.resolve_reference("org-a", "cred-unknown")


# ---------------------------------------------------------------------------
# Gap 1: Auto-provisioning via IntegrationManager.connect()
# ---------------------------------------------------------------------------

def test_connect_auto_provisions_n8n_credential_and_registers_mapping():
    """connect() must call create_credential on n8n and register the mapping automatically."""
    # First response: n8n's create_credential response
    client, session = client_with(FakeResponse(data={"id": "n8n-cred-auto"}))
    provider = N8nCredentialProvider()
    manager = IntegrationManager(n8n_client=client, n8n_credential_provider=provider)

    connection = manager.connect("org-a", "crm", "FAKE_SECRET")

    # Exactly one call to n8n: create_credential
    assert len(session.calls) == 1
    assert "/api/v1/credentials" in session.calls[0][1]
    # The raw secret must NOT appear in the URL or logged payload keys
    assert "FAKE_SECRET" not in session.calls[0][1]

    # The mapping must be resolvable immediately after connect()
    n8n_ref = provider.resolve_reference("org-a", connection.credential_reference)
    assert n8n_ref.id == "n8n-cred-auto"
    assert n8n_ref.organization_id == "org-a"


def test_connect_auto_provisioning_failure_rolls_back_credential():
    """If n8n provisioning fails, the Voice2Flow credential must be revoked and no connection stored."""
    # n8n returns an error (500)
    client, _ = client_with(FakeResponse(status_code=500, data={}))
    manager = IntegrationManager(n8n_client=client)

    with pytest.raises(Exception):
        manager.connect("org-a", "crm", "FAKE_SECRET")

    # No connection must be stored
    with pytest.raises(LookupError):
        manager.get_connection("org-a", "crm")

    # The Voice2Flow credential must be revoked (not resolvable)
    from backend.integrations.credential_manager import CredentialError
    for ref_id, ref in manager.credentials._references.items():
        # Any credential created for org-a/crm must be revoked
        if ref.organization_id == "org-a" and ref.integration == "crm":
            assert ref.status == "revoked", f"Credential {ref_id} was not revoked after provisioning failure"


def test_connect_without_n8n_client_skips_provisioning():
    """When no n8n_client is configured, connect() completes without n8n calls."""
    manager = IntegrationManager()  # no n8n_client
    connection = manager.connect("org-a", "crm", "FAKE_SECRET")
    assert connection.status == "connected"
    # resolve_reference on the provider should raise because no mapping was registered
    with pytest.raises(N8nCredentialError):
        manager.n8n_credential_provider.resolve_reference("org-a", connection.credential_reference)


def test_cross_tenant_isolation_after_auto_provisioning():
    """org-b must not be able to resolve org-a's auto-provisioned n8n credential."""
    client, _ = client_with(FakeResponse(data={"id": "n8n-cred-org-a"}))
    manager = IntegrationManager(n8n_client=client)
    connection = manager.connect("org-a", "crm", "FAKE_SECRET")

    with pytest.raises(N8nCredentialError):
        manager.n8n_credential_provider.resolve_reference("org-b", connection.credential_reference)


def test_execution_uses_manager_provider_and_n8n_client_without_raw_secret():
    # connect() now auto-provisions via create_credential (first call),
    # then execute_workflow is the second call.
    client, session = client_with(
        FakeResponse(data={"id": "n8n-cred-1"}),                              # create_credential during connect()
        FakeResponse(data={"executionId": "exec-1", "data": {"ok": True}}),   # execute_workflow
    )
    provider = N8nCredentialProvider()
    manager = IntegrationManager(n8n_client=client, n8n_credential_provider=provider)
    # connect() auto-provisions — no manual register_mapping needed
    manager.connect("org-a", "crm", "FAKE_SECRET")
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    result = execute_plan({
        "steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {"status": "delayed"}}]
    }, context)

    assert result["step_1"]["execution_id"] == "exec-1"
    # The execute_workflow call is session.calls[1]
    payload = session.calls[1][2]["json"]
    assert payload["credential_id"] == "n8n-cred-1"
    assert "FAKE_SECRET" not in str(payload)


def test_execution_rejects_unmapped_n8n_credential():
    """When no n8n_client is on the manager, resolve_reference must raise ExecutionError."""
    # Manager has no n8n_client → connect() skips provisioning → resolve_reference raises
    manager = IntegrationManager()  # no n8n_client
    # Attach a real n8n_client ONLY to trigger the resolve path, without registering a mapping
    # We simulate this by giving the manager a client only at execution time via a patched object.
    # Easier: create a manager with n8n_client but no n8n responses → provisioning fails.
    # Actually the cleanest approach: use a manager with n8n_client set, connect without provisioning
    # by directly calling credentials.create_credential and _connections, bypassing connect().
    from backend.integrations.credential_manager import CredentialManager
    from backend.integrations.persistence import IntegrationStateStore
    from backend.integrations.connection_manager import IntegrationConnection
    from datetime import datetime, timezone

    store = IntegrationStateStore(":memory:")
    cred_manager = CredentialManager(store)
    provider = N8nCredentialProvider()
    # Fake client (no n8n_client on the manager so it exercises the resolve path)
    fake_client, _ = client_with()
    manager2 = IntegrationManager(
        credential_manager=cred_manager,
        state_store=store,
        n8n_client=fake_client,
        n8n_credential_provider=provider,
    )
    # Manually insert a connection + credential reference WITHOUT registering an n8n mapping
    ref = cred_manager.create_credential("org-a", "crm", "FAKE_SECRET")
    now = datetime.now(timezone.utc).isoformat()
    conn = IntegrationConnection(
        id="conn_test",
        organization_id="org-a",
        integration="crm",
        status="connected",
        credential_reference=ref.id,
        account_identifier=None,
        created_at=now,
        updated_at=now,
    )
    manager2._connections[("org-a", "crm")] = conn

    context = ConversationContext("user-a", "org-a", integration_manager=manager2)
    with pytest.raises(ExecutionError, match="not mapped"):
        execute_plan({
            "steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {}}]
        }, context)

