"""
Unit tests for the OpenStack VM Lifecycle API.
Run with: pytest tests/ -v
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.openstack_client import _MOCK_VMS


@pytest.fixture(autouse=True)
def clear_vms():
    """Ensure a clean VM store for each test."""
    _MOCK_VMS.clear()
    yield
    _MOCK_VMS.clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Health ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.anyio
async def test_root(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "docs" in r.json()


# ── Flavors ────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_flavors(client):
    r = await client.get("/api/v1/flavors")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 5
    assert len(body["flavors"]) == body["total"]


@pytest.mark.anyio
async def test_get_flavor_valid(client):
    r = await client.get("/api/v1/flavors/m1.small")
    assert r.status_code == 200
    f = r.json()
    assert f["id"] == "m1.small"
    assert f["vcpus"] == 1


@pytest.mark.anyio
async def test_get_flavor_not_found(client):
    r = await client.get("/api/v1/flavors/nonexistent-flavor")
    assert r.status_code == 404
    assert r.json()["error"] == "FLAVOR_NOT_FOUND"


# ── Images ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_images(client):
    r = await client.get("/api/v1/images")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 4


@pytest.mark.anyio
async def test_get_image_valid(client):
    r = await client.get("/api/v1/images/img-ubuntu-22")
    assert r.status_code == 200
    assert "Ubuntu" in r.json()["name"]


@pytest.mark.anyio
async def test_get_image_not_found(client):
    r = await client.get("/api/v1/images/img-nonexistent")
    assert r.status_code == 404
    assert r.json()["error"] == "IMAGE_NOT_FOUND"


# ── VM CRUD ────────────────────────────────────────────────────────────────────

VM_PAYLOAD = {
    "name": "test-vm",
    "flavor_id": "m1.small",
    "image_id": "img-ubuntu-22",
    "network_ids": ["net-123"],
    "security_groups": ["default"],
    "metadata": {"env": "test"},
}


@pytest.mark.anyio
async def test_create_vm(client):
    r = await client.post("/api/v1/vms", json=VM_PAYLOAD)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "test-vm"
    assert body["status"] == "BUILD"
    assert "id" in body


@pytest.mark.anyio
async def test_list_vms_empty(client):
    r = await client.get("/api/v1/vms")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.anyio
async def test_list_vms_with_vm(client):
    await client.post("/api/v1/vms", json=VM_PAYLOAD)
    r = await client.get("/api/v1/vms")
    assert r.json()["total"] == 1


@pytest.mark.anyio
async def test_get_vm(client):
    create_r = await client.post("/api/v1/vms", json=VM_PAYLOAD)
    vm_id = create_r.json()["id"]
    r = await client.get(f"/api/v1/vms/{vm_id}")
    assert r.status_code == 200
    assert r.json()["id"] == vm_id


@pytest.mark.anyio
async def test_get_vm_not_found(client):
    r = await client.get("/api/v1/vms/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"] == "VM_NOT_FOUND"


@pytest.mark.anyio
async def test_delete_vm(client):
    create_r = await client.post("/api/v1/vms", json=VM_PAYLOAD)
    vm_id = create_r.json()["id"]
    del_r = await client.delete(f"/api/v1/vms/{vm_id}")
    assert del_r.status_code == 204
    # Confirm gone
    get_r = await client.get(f"/api/v1/vms/{vm_id}")
    assert get_r.status_code == 404


# ── VM Lifecycle Actions ───────────────────────────────────────────────────────

async def _create_active_vm(client) -> str:
    """Helper: create a VM and manually force it ACTIVE."""
    r = await client.post("/api/v1/vms", json=VM_PAYLOAD)
    vm_id = r.json()["id"]
    # Manually flip to ACTIVE (simulate build completion)
    _MOCK_VMS[vm_id]["status"] = "ACTIVE"
    _MOCK_VMS[vm_id]["power_state"] = 1
    return vm_id


@pytest.mark.anyio
async def test_stop_vm(client):
    vm_id = await _create_active_vm(client)
    r = await client.post(f"/api/v1/vms/{vm_id}/stop")
    assert r.status_code == 200
    assert r.json()["action"] == "stop"
    vm_r = await client.get(f"/api/v1/vms/{vm_id}")
    assert vm_r.json()["status"] == "SHUTOFF"


@pytest.mark.anyio
async def test_start_vm(client):
    vm_id = await _create_active_vm(client)
    _MOCK_VMS[vm_id]["status"] = "SHUTOFF"
    r = await client.post(f"/api/v1/vms/{vm_id}/start")
    assert r.status_code == 200
    assert r.json()["action"] == "start"
    vm_r = await client.get(f"/api/v1/vms/{vm_id}")
    assert vm_r.json()["status"] == "ACTIVE"


@pytest.mark.anyio
async def test_reboot_vm(client):
    vm_id = await _create_active_vm(client)
    r = await client.post(f"/api/v1/vms/{vm_id}/reboot", json={"reboot_type": "SOFT"})
    assert r.status_code == 200
    assert "reboot" in r.json()["action"]


@pytest.mark.anyio
async def test_stop_non_active_vm_returns_409(client):
    vm_id = await _create_active_vm(client)
    _MOCK_VMS[vm_id]["status"] = "SHUTOFF"
    r = await client.post(f"/api/v1/vms/{vm_id}/stop")
    assert r.status_code == 409
    assert r.json()["error"] == "INVALID_VM_STATE"


@pytest.mark.anyio
async def test_resize_vm(client):
    vm_id = await _create_active_vm(client)
    r = await client.post(f"/api/v1/vms/{vm_id}/resize", json={"flavor_id": "m1.medium"})
    assert r.status_code == 200
    assert r.json()["action"] == "resize"


@pytest.mark.anyio
async def test_update_metadata(client):
    vm_id = await _create_active_vm(client)
    r = await client.patch(f"/api/v1/vms/{vm_id}/metadata", json={"metadata": {"team": "platform"}})
    assert r.status_code == 200
    assert r.json()["metadata"]["team"] == "platform"


# ── Validation ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_vm_invalid_name(client):
    payload = {**VM_PAYLOAD, "name": "invalid name with spaces!"}
    r = await client.post("/api/v1/vms", json=payload)
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_vm_missing_networks(client):
    payload = {**VM_PAYLOAD, "network_ids": []}
    r = await client.post("/api/v1/vms", json=payload)
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_vm_bad_flavor(client):
    payload = {**VM_PAYLOAD, "flavor_id": "nonexistent"}
    r = await client.post("/api/v1/vms", json=payload)
    assert r.status_code == 404


@pytest.mark.anyio
async def test_pagination(client):
    for i in range(5):
        await client.post("/api/v1/vms", json={**VM_PAYLOAD, "name": f"vm-{i:02d}"})
    r = await client.get("/api/v1/vms?page=1&page_size=3")
    body = r.json()
    assert len(body["vms"]) == 3
    assert body["total"] == 5
    assert body["has_next"] is True


@pytest.mark.anyio
async def test_filter_by_status(client):
    await client.post("/api/v1/vms", json=VM_PAYLOAD)
    r = await client.get("/api/v1/vms?status=ACTIVE")
    # all VMs start in BUILD, so 0 ACTIVE
    assert r.json()["total"] == 0


# ── Request metadata headers ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_request_id_header(client):
    r = await client.get("/health")
    assert "x-request-id" in r.headers
    assert "x-process-time" in r.headers
