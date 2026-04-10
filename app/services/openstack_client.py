"""
OpenStack client service.

Supports two modes:
  - MOCK_MODE=True  → Returns realistic in-memory fake data (no real OpenStack needed)
  - MOCK_MODE=False → Connects to a real OpenStack deployment via keystoneauth1 + novaclient
"""

import asyncio
import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.exceptions import (
    FlavorNotFoundError,
    ImageNotFoundError,
    InvalidVMStateError,
    OpenStackConnectionError,
    QuotaExceededError,
    VMNotFoundError,
)

logger = logging.getLogger(__name__)

# ── Mock data store ────────────────────────────────────────────────────────────

_MOCK_FLAVORS = [
    {"id": "m1.tiny",   "name": "m1.tiny",   "vcpus": 1, "ram_mb": 512,   "disk_gb": 1,  "ephemeral_gb": 0, "swap_mb": 0, "rxtx_factor": 1.0, "is_public": True},
    {"id": "m1.small",  "name": "m1.small",  "vcpus": 1, "ram_mb": 2048,  "disk_gb": 20, "ephemeral_gb": 0, "swap_mb": 0, "rxtx_factor": 1.0, "is_public": True},
    {"id": "m1.medium", "name": "m1.medium", "vcpus": 2, "ram_mb": 4096,  "disk_gb": 40, "ephemeral_gb": 0, "swap_mb": 0, "rxtx_factor": 1.0, "is_public": True},
    {"id": "m1.large",  "name": "m1.large",  "vcpus": 4, "ram_mb": 8192,  "disk_gb": 80, "ephemeral_gb": 0, "swap_mb": 0, "rxtx_factor": 1.0, "is_public": True},
    {"id": "m1.xlarge", "name": "m1.xlarge", "vcpus": 8, "ram_mb": 16384, "disk_gb": 160,"ephemeral_gb": 0, "swap_mb": 0, "rxtx_factor": 1.0, "is_public": True},
    {"id": "c1.medium", "name": "c1.medium", "vcpus": 4, "ram_mb": 2048,  "disk_gb": 40, "ephemeral_gb": 0, "swap_mb": 0, "rxtx_factor": 1.0, "is_public": True},
    {"id": "r1.large",  "name": "r1.large",  "vcpus": 2, "ram_mb": 16384, "disk_gb": 40, "ephemeral_gb": 0, "swap_mb": 0, "rxtx_factor": 1.0, "is_public": True},
]

_MOCK_IMAGES = [
    {"id": "img-ubuntu-22", "name": "Ubuntu 22.04 LTS", "status": "active", "size_bytes": 629145600, "min_disk_gb": 8,  "min_ram_mb": 512,  "disk_format": "qcow2", "container_format": "bare", "visibility": "public", "created_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC), "tags": ["ubuntu", "lts"], "properties": {"os_type": "linux", "os_distro": "ubuntu"}},
    {"id": "img-ubuntu-20", "name": "Ubuntu 20.04 LTS", "status": "active", "size_bytes": 629145600, "min_disk_gb": 8,  "min_ram_mb": 512,  "disk_format": "qcow2", "container_format": "bare", "visibility": "public", "created_at": datetime(2024, 1, 10, 12, 0, 0, tzinfo=UTC), "tags": ["ubuntu", "lts"], "properties": {"os_type": "linux", "os_distro": "ubuntu"}},
    {"id": "img-centos-9",  "name": "CentOS Stream 9",  "status": "active", "size_bytes": 524288000, "min_disk_gb": 10, "min_ram_mb": 1024, "disk_format": "qcow2", "container_format": "bare", "visibility": "public", "created_at": datetime(2024, 2, 1, 12, 0, 0, tzinfo=UTC), "tags": ["centos"], "properties": {"os_type": "linux", "os_distro": "centos"}},
    {"id": "img-debian-12", "name": "Debian 12 Bookworm","status": "active", "size_bytes": 419430400, "min_disk_gb": 8,  "min_ram_mb": 512,  "disk_format": "qcow2", "container_format": "bare", "visibility": "public", "created_at": datetime(2024, 1, 20, 12, 0, 0, tzinfo=UTC), "tags": ["debian"], "properties": {"os_type": "linux", "os_distro": "debian"}},
    {"id": "img-rhel-9",    "name": "RHEL 9.2",         "status": "active", "size_bytes": 786432000, "min_disk_gb": 10, "min_ram_mb": 1024, "disk_format": "qcow2", "container_format": "bare", "visibility": "private","created_at": datetime(2024, 3, 1, 12, 0, 0, tzinfo=UTC), "tags": ["rhel", "enterprise"], "properties": {"os_type": "linux", "os_distro": "rhel"}},
]

# In-memory VM store: id -> dict
_MOCK_VMS: dict[str, dict[str, Any]] = {}


def _make_mock_vm(name: str, flavor_id: str, image_id: str, network_ids: list[str],
                   key_name: str | None, security_groups: list[str],
                   user_data: str | None, availability_zone: str | None,
                   metadata: dict[str, str]) -> dict[str, Any]:
    flavor = next((f for f in _MOCK_FLAVORS if f["id"] == flavor_id), None)
    if not flavor:
        raise FlavorNotFoundError(flavor_id)
    image = next((i for i in _MOCK_IMAGES if i["id"] == image_id), None)
    if not image:
        raise ImageNotFoundError(image_id)

    vm_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    networks = {}
    for net_id in network_ids:
        networks[net_id] = [
            {
                "ip_address": f"10.0.{random.randint(0, 254)}.{random.randint(2, 254)}",
                "ip_version": 4,
                "mac_address": ":".join(f"{random.randint(0,255):02x}" for _ in range(6)),
                "network_type": "fixed",
            }
        ]

    return {
        "id": vm_id,
        "name": name,
        "status": "BUILD",
        "flavor": {"id": flavor["id"], "name": flavor["name"], "vcpus": flavor["vcpus"], "ram_mb": flavor["ram_mb"], "disk_gb": flavor["disk_gb"]},
        "image": {"id": image["id"], "name": image["name"]},
        "networks": networks,
        "key_name": key_name,
        "security_groups": security_groups,
        "availability_zone": availability_zone or "nova",
        "metadata": metadata,
        "created_at": now,
        "updated_at": now,
        "host": f"compute-{random.randint(1, 5):02d}",
        "tenant_id": "demo-tenant-id",
        "user_id": "demo-user-id",
        "power_state": 0,
        "task_state": "spawning",
        "progress": 0,
    }


class OpenStackClient:
    """
    Async client abstracting OpenStack Nova + Glance operations.

    In MOCK_MODE it simulates real behaviour (BUILD→ACTIVE transition,
    state guards, etc.) without needing an actual OpenStack environment.
    When MOCK_MODE is False it delegates to keystoneauth1 + novaclient
    (install extras: pip install openstack-vm-api[openstack]).
    """

    def __init__(self):
        self.mock_mode = settings.MOCK_MODE
        self._nova = None  # lazy-initialised in real mode

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _get_nova(self):
        """Return authenticated Nova client (real mode only)."""
        if self._nova is not None:
            return self._nova
        try:
            from keystoneauth1 import loading, session
            from novaclient import client as nova_client

            loader = loading.get_plugin_loader("password")
            auth = loader.load_from_options(
                auth_url=settings.OS_AUTH_URL,
                username=settings.OS_USERNAME,
                password=settings.OS_PASSWORD,
                project_name=settings.OS_PROJECT_NAME,
                user_domain_name=settings.OS_USER_DOMAIN_NAME,
                project_domain_name=settings.OS_PROJECT_DOMAIN_NAME,
            )
            sess = session.Session(auth=auth)
            self._nova = nova_client.Client(
                settings.OS_COMPUTE_API_VERSION,
                session=sess,
                region_name=settings.OS_REGION_NAME,
            )
            return self._nova
        except Exception as e:
            raise OpenStackConnectionError(f"Cannot connect to OpenStack: {e}")

    async def _simulate_build(self, vm_id: str):
        """Background task: transition mock VM BUILD → ACTIVE after a delay."""
        await asyncio.sleep(2)
        if vm_id in _MOCK_VMS:
            _MOCK_VMS[vm_id]["status"] = "ACTIVE"
            _MOCK_VMS[vm_id]["task_state"] = None
            _MOCK_VMS[vm_id]["power_state"] = 1
            _MOCK_VMS[vm_id]["progress"] = 100
            _MOCK_VMS[vm_id]["updated_at"] = datetime.now(UTC)
            logger.info(f"Mock VM {vm_id} transitioned BUILD → ACTIVE")

    # ── Connectivity ───────────────────────────────────────────────────────────

    async def check_connectivity(self) -> bool:
        if self.mock_mode:
            return True
        try:
            nova = await self._get_nova()
            nova.servers.list(limit=1)
            return True
        except Exception:
            return False

    # ── VM operations ──────────────────────────────────────────────────────────

    async def list_vms(self, status: str | None = None, page: int = 1,
                        page_size: int = 20, search: str | None = None) -> dict[str, Any]:
        if self.mock_mode:
            vms = list(_MOCK_VMS.values())
            if status:
                vms = [v for v in vms if v["status"] == status.upper()]
            if search:
                vms = [v for v in vms if search.lower() in v["name"].lower()]
            total = len(vms)
            start = (page - 1) * page_size
            end = start + page_size
            return {
                "vms": vms[start:end],
                "total": total,
                "page": page,
                "page_size": page_size,
                "has_next": end < total,
            }

        nova = await self._get_nova()
        kwargs = {"limit": page_size}
        if status:
            kwargs["status"] = status
        if search:
            kwargs["name"] = search
        servers = nova.servers.list(search_opts=kwargs)
        return {
            "vms": [self._serialize_server(s) for s in servers],
            "total": len(servers),
            "page": page,
            "page_size": page_size,
            "has_next": False,
        }

    async def get_vm(self, vm_id: str) -> dict[str, Any]:
        if self.mock_mode:
            vm = _MOCK_VMS.get(vm_id)
            if not vm:
                raise VMNotFoundError(vm_id)
            return vm

        nova = await self._get_nova()
        try:
            server = nova.servers.get(vm_id)
            return self._serialize_server(server)
        except Exception:
            raise VMNotFoundError(vm_id)

    async def create_vm(self, name: str, flavor_id: str, image_id: str,
                         network_ids: list[str], key_name: str | None = None,
                         security_groups: list[str] | None = None,
                         user_data: str | None = None,
                         availability_zone: str | None = None,
                         metadata: dict[str, str] | None = None) -> dict[str, Any]:
        security_groups = security_groups or ["default"]
        metadata = metadata or {}

        if self.mock_mode:
            if len(_MOCK_VMS) >= 20:
                raise QuotaExceededError("instances")
            vm = _make_mock_vm(name, flavor_id, image_id, network_ids,
                                key_name, security_groups, user_data,
                                availability_zone, metadata)
            _MOCK_VMS[vm["id"]] = vm
            asyncio.create_task(self._simulate_build(vm["id"]))
            logger.info(f"Mock VM created: {vm['id']} ({name})")
            return vm

        nova = await self._get_nova()
        nics = [{"net-id": nid} for nid in network_ids]
        sgs = [{"name": sg} for sg in security_groups]
        server = nova.servers.create(
            name=name,
            flavor=flavor_id,
            image=image_id,
            nics=nics,
            key_name=key_name,
            security_groups=sgs,
            userdata=user_data,
            availability_zone=availability_zone,
            meta=metadata,
        )
        return self._serialize_server(server)

    async def start_vm(self, vm_id: str) -> None:
        if self.mock_mode:
            vm = _MOCK_VMS.get(vm_id)
            if not vm:
                raise VMNotFoundError(vm_id)
            if vm["status"] not in ("SHUTOFF", "SUSPENDED"):
                raise InvalidVMStateError(vm_id, vm["status"], "SHUTOFF or SUSPENDED")
            vm["status"] = "ACTIVE"
            vm["power_state"] = 1
            vm["updated_at"] = datetime.now(UTC)
            return

        nova = await self._get_nova()
        try:
            server = nova.servers.get(vm_id)
        except Exception:
            raise VMNotFoundError(vm_id)
        server.start()

    async def stop_vm(self, vm_id: str) -> None:
        if self.mock_mode:
            vm = _MOCK_VMS.get(vm_id)
            if not vm:
                raise VMNotFoundError(vm_id)
            if vm["status"] != "ACTIVE":
                raise InvalidVMStateError(vm_id, vm["status"], "ACTIVE")
            vm["status"] = "SHUTOFF"
            vm["power_state"] = 4
            vm["updated_at"] = datetime.now(UTC)
            return

        nova = await self._get_nova()
        try:
            server = nova.servers.get(vm_id)
        except Exception:
            raise VMNotFoundError(vm_id)
        server.stop()

    async def reboot_vm(self, vm_id: str, reboot_type: str = "SOFT") -> None:
        if self.mock_mode:
            vm = _MOCK_VMS.get(vm_id)
            if not vm:
                raise VMNotFoundError(vm_id)
            if vm["status"] != "ACTIVE":
                raise InvalidVMStateError(vm_id, vm["status"], "ACTIVE")
            vm["status"] = "REBOOT" if reboot_type == "SOFT" else "HARD_REBOOT"
            vm["updated_at"] = datetime.now(UTC)
            asyncio.create_task(self._simulate_reboot(vm_id))
            return

        nova = await self._get_nova()
        try:
            server = nova.servers.get(vm_id)
        except Exception:
            raise VMNotFoundError(vm_id)
        server.reboot(reboot_type=reboot_type)

    async def _simulate_reboot(self, vm_id: str):
        await asyncio.sleep(3)
        if vm_id in _MOCK_VMS:
            _MOCK_VMS[vm_id]["status"] = "ACTIVE"
            _MOCK_VMS[vm_id]["updated_at"] = datetime.now(UTC)

    async def resize_vm(self, vm_id: str, flavor_id: str) -> None:
        if self.mock_mode:
            vm = _MOCK_VMS.get(vm_id)
            if not vm:
                raise VMNotFoundError(vm_id)
            if vm["status"] != "ACTIVE":
                raise InvalidVMStateError(vm_id, vm["status"], "ACTIVE")
            flavor = next((f for f in _MOCK_FLAVORS if f["id"] == flavor_id), None)
            if not flavor:
                raise FlavorNotFoundError(flavor_id)
            vm["status"] = "RESIZE"
            vm["updated_at"] = datetime.now(UTC)
            asyncio.create_task(self._simulate_resize(vm_id, flavor))
            return

        nova = await self._get_nova()
        try:
            server = nova.servers.get(vm_id)
        except Exception:
            raise VMNotFoundError(vm_id)
        server.resize(flavor_id)

    async def _simulate_resize(self, vm_id: str, flavor: dict):
        await asyncio.sleep(3)
        if vm_id in _MOCK_VMS:
            _MOCK_VMS[vm_id]["flavor"] = {
                "id": flavor["id"], "name": flavor["name"],
                "vcpus": flavor["vcpus"], "ram_mb": flavor["ram_mb"], "disk_gb": flavor["disk_gb"],
            }
            _MOCK_VMS[vm_id]["status"] = "VERIFY_RESIZE"
            _MOCK_VMS[vm_id]["updated_at"] = datetime.now(UTC)

    async def confirm_resize_vm(self, vm_id: str) -> None:
        if self.mock_mode:
            vm = _MOCK_VMS.get(vm_id)
            if not vm:
                raise VMNotFoundError(vm_id)
            if vm["status"] != "VERIFY_RESIZE":
                raise InvalidVMStateError(vm_id, vm["status"], "VERIFY_RESIZE")
            vm["status"] = "ACTIVE"
            vm["updated_at"] = datetime.now(UTC)
            return

        nova = await self._get_nova()
        try:
            server = nova.servers.get(vm_id)
        except Exception:
            raise VMNotFoundError(vm_id)
        server.confirm_resize()

    async def delete_vm(self, vm_id: str) -> None:
        if self.mock_mode:
            if vm_id not in _MOCK_VMS:
                raise VMNotFoundError(vm_id)
            _MOCK_VMS[vm_id]["status"] = "DELETED"
            del _MOCK_VMS[vm_id]
            logger.info(f"Mock VM deleted: {vm_id}")
            return

        nova = await self._get_nova()
        try:
            server = nova.servers.get(vm_id)
        except Exception:
            raise VMNotFoundError(vm_id)
        server.delete()

    async def update_vm_metadata(self, vm_id: str, metadata: dict[str, str]) -> dict[str, Any]:
        if self.mock_mode:
            vm = _MOCK_VMS.get(vm_id)
            if not vm:
                raise VMNotFoundError(vm_id)
            vm["metadata"].update(metadata)
            vm["updated_at"] = datetime.now(UTC)
            return vm

        nova = await self._get_nova()
        try:
            server = nova.servers.get(vm_id)
        except Exception:
            raise VMNotFoundError(vm_id)
        server.set_meta(metadata)
        return self._serialize_server(server)

    # ── Flavor operations ──────────────────────────────────────────────────────

    async def list_flavors(self) -> list[dict[str, Any]]:
        if self.mock_mode:
            return _MOCK_FLAVORS

        nova = await self._get_nova()
        return [self._serialize_flavor(f) for f in nova.flavors.list()]

    async def get_flavor(self, flavor_id: str) -> dict[str, Any]:
        if self.mock_mode:
            flavor = next((f for f in _MOCK_FLAVORS if f["id"] == flavor_id), None)
            if not flavor:
                raise FlavorNotFoundError(flavor_id)
            return flavor

        nova = await self._get_nova()
        try:
            return self._serialize_flavor(nova.flavors.get(flavor_id))
        except Exception:
            raise FlavorNotFoundError(flavor_id)

    # ── Image operations ───────────────────────────────────────────────────────

    async def list_images(self) -> list[dict[str, Any]]:
        if self.mock_mode:
            return _MOCK_IMAGES

        nova = await self._get_nova()
        return [self._serialize_image(i) for i in nova.glance.list()]

    async def get_image(self, image_id: str) -> dict[str, Any]:
        if self.mock_mode:
            image = next((i for i in _MOCK_IMAGES if i["id"] == image_id), None)
            if not image:
                raise ImageNotFoundError(image_id)
            return image

        nova = await self._get_nova()
        try:
            return self._serialize_image(nova.glance.find_image(image_id))
        except Exception:
            raise ImageNotFoundError(image_id)

    # ── Serializers (real mode) ────────────────────────────────────────────────

    def _serialize_server(self, server) -> dict[str, Any]:
        networks = {}
        for net_name, addresses in getattr(server, "addresses", {}).items():
            networks[net_name] = [
                {
                    "ip_address": a.get("addr"),
                    "ip_version": a.get("version", 4),
                    "mac_address": a.get("OS-EXT-IPS-MAC:mac_addr"),
                    "network_type": a.get("OS-EXT-IPS:type"),
                }
                for a in addresses
            ]
        flavor_info = getattr(server, "flavor", {})
        image_info = getattr(server, "image", {}) or {}
        return {
            "id": server.id,
            "name": server.name,
            "status": server.status,
            "flavor": {
                "id": flavor_info.get("id", ""),
                "name": flavor_info.get("id", ""),
                "vcpus": 0, "ram_mb": 0, "disk_gb": 0,
            },
            "image": {"id": image_info.get("id", ""), "name": image_info.get("id", "")},
            "networks": networks,
            "key_name": getattr(server, "key_name", None),
            "security_groups": [sg["name"] for sg in getattr(server, "security_groups", [])],
            "availability_zone": getattr(server, "OS-EXT-AZ:availability_zone", None),
            "metadata": getattr(server, "metadata", {}),
            "created_at": datetime.fromisoformat(server.created.replace("Z", "+00:00")),
            "updated_at": datetime.fromisoformat(server.updated.replace("Z", "+00:00")),
            "host": getattr(server, "OS-EXT-SRV-ATTR:host", None),
            "tenant_id": getattr(server, "tenant_id", None),
            "user_id": getattr(server, "user_id", None),
            "power_state": getattr(server, "OS-EXT-STS:power_state", None),
            "task_state": getattr(server, "OS-EXT-STS:task_state", None),
            "progress": getattr(server, "progress", None),
        }

    def _serialize_flavor(self, flavor) -> dict[str, Any]:
        return {
            "id": flavor.id,
            "name": flavor.name,
            "vcpus": flavor.vcpus,
            "ram_mb": flavor.ram,
            "disk_gb": flavor.disk,
            "ephemeral_gb": getattr(flavor, "OS-FLV-EXT-DATA:ephemeral", 0),
            "swap_mb": flavor.swap or 0,
            "rxtx_factor": getattr(flavor, "rxtx_factor", 1.0),
            "is_public": getattr(flavor, "os-flavor-access:is_public", True),
        }

    def _serialize_image(self, image) -> dict[str, Any]:
        return {
            "id": image.id,
            "name": image.name,
            "status": image.status,
            "size_bytes": getattr(image, "size", None),
            "min_disk_gb": getattr(image, "minDisk", 0),
            "min_ram_mb": getattr(image, "minRam", 0),
            "disk_format": getattr(image, "disk_format", None),
            "container_format": getattr(image, "container_format", None),
            "visibility": getattr(image, "visibility", "public"),
            "created_at": datetime.fromisoformat(image.created.replace("Z", "+00:00")),
            "updated_at": datetime.fromisoformat(image.updated.replace("Z", "+00:00")),
            "tags": getattr(image, "tags", []),
            "properties": {},
        }


# Singleton
openstack_client = OpenStackClient()
