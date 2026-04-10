"""Pydantic schemas for VM lifecycle API request and response models."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class VMStatus(StrEnum):
    ACTIVE = "ACTIVE"
    BUILD = "BUILD"
    DELETED = "DELETED"
    ERROR = "ERROR"
    HARD_REBOOT = "HARD_REBOOT"
    MIGRATING = "MIGRATING"
    PAUSED = "PAUSED"
    REBOOT = "REBOOT"
    REBUILD = "REBUILD"
    RESCUE = "RESCUE"
    RESIZE = "RESIZE"
    REVERT_RESIZE = "REVERT_RESIZE"
    SHELVED = "SHELVED"
    SHELVED_OFFLOADED = "SHELVED_OFFLOADED"
    SHUTOFF = "SHUTOFF"
    SOFT_DELETED = "SOFT_DELETED"
    SUSPENDED = "SUSPENDED"
    UNKNOWN = "UNKNOWN"
    VERIFY_RESIZE = "VERIFY_RESIZE"


class RebootType(StrEnum):
    SOFT = "SOFT"
    HARD = "HARD"


# ── Nested models ─────────────────────────────────────────────────────────────

class NetworkAddress(BaseModel):
    ip_address: str
    ip_version: int = Field(ge=4, le=6)
    mac_address: str | None = None
    network_type: str | None = None


class FlavorSummary(BaseModel):
    id: str
    name: str
    vcpus: int
    ram_mb: int
    disk_gb: int


class ImageSummary(BaseModel):
    id: str
    name: str


class VMMetadata(BaseModel):
    key: str
    value: str


# ── Request schemas ────────────────────────────────────────────────────────────

class VMCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="VM display name")
    flavor_id: str = Field(..., description="ID of the flavor (CPU/RAM/disk profile)")
    image_id: str = Field(..., description="ID of the base OS image")
    network_ids: list[str] = Field(..., min_length=1, description="One or more network IDs to attach")
    key_name: str | None = Field(None, description="SSH keypair name for access")
    security_groups: list[str] = Field(default=["default"], description="Security group names")
    user_data: str | None = Field(None, description="Base64-encoded cloud-init user data")
    availability_zone: str | None = Field(None, description="Target availability zone")
    metadata: dict[str, str] | None = Field(default_factory=dict, description="Arbitrary key-value metadata")

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v: str) -> str:
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Name must contain only alphanumeric characters, hyphens, or underscores")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "web-server-01",
                "flavor_id": "m1.small",
                "image_id": "ubuntu-22.04-amd64",
                "network_ids": ["private-net-id"],
                "key_name": "my-keypair",
                "security_groups": ["default", "web-sg"],
                "metadata": {"env": "production", "team": "platform"},
            }
        }
    }


class VMRebootRequest(BaseModel):
    reboot_type: RebootType = Field(
        default=RebootType.SOFT,
        description="SOFT (graceful) or HARD (forced) reboot",
    )

    model_config = {"json_schema_extra": {"example": {"reboot_type": "SOFT"}}}


class VMResizeRequest(BaseModel):
    flavor_id: str = Field(..., description="Target flavor ID to resize to")

    model_config = {"json_schema_extra": {"example": {"flavor_id": "m1.medium"}}}


class VMMetadataUpdateRequest(BaseModel):
    metadata: dict[str, str] = Field(..., description="Metadata key-value pairs to set/update")

    model_config = {"json_schema_extra": {"example": {"metadata": {"env": "staging", "version": "2.1"}}}}


# ── Response schemas ───────────────────────────────────────────────────────────

class VMResponse(BaseModel):
    id: str
    name: str
    status: VMStatus
    flavor: FlavorSummary
    image: ImageSummary
    networks: dict[str, list[NetworkAddress]] = Field(default_factory=dict)
    key_name: str | None = None
    security_groups: list[str] = Field(default_factory=list)
    availability_zone: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None
    host: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    power_state: int | None = None
    task_state: str | None = None
    progress: int | None = Field(None, ge=0, le=100)

    model_config = {"from_attributes": True}


class VMListResponse(BaseModel):
    vms: list[VMResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class VMActionResponse(BaseModel):
    vm_id: str
    action: str
    status: str
    message: str


class FlavorResponse(BaseModel):
    id: str
    name: str
    vcpus: int
    ram_mb: int
    disk_gb: int
    ephemeral_gb: int = 0
    swap_mb: int = 0
    rxtx_factor: float = 1.0
    is_public: bool = True
    description: str | None = None
    extra_specs: dict[str, str] = Field(default_factory=dict)


class FlavorListResponse(BaseModel):
    flavors: list[FlavorResponse]
    total: int


class ImageResponse(BaseModel):
    id: str
    name: str
    status: str
    size_bytes: int | None = None
    min_disk_gb: int = 0
    min_ram_mb: int = 0
    disk_format: str | None = None
    container_format: str | None = None
    visibility: str = "public"
    created_at: datetime
    updated_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class ImageListResponse(BaseModel):
    images: list[ImageResponse]
    total: int


class ErrorResponse(BaseModel):
    error: str
    message: str
    request_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str
