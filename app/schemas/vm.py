"""Pydantic schemas for VM lifecycle API request and response models."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class VMStatus(str, Enum):
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


class RebootType(str, Enum):
    SOFT = "SOFT"
    HARD = "HARD"


# ── Nested models ─────────────────────────────────────────────────────────────

class NetworkAddress(BaseModel):
    ip_address: str
    ip_version: int = Field(ge=4, le=6)
    mac_address: Optional[str] = None
    network_type: Optional[str] = None


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
    network_ids: List[str] = Field(..., min_length=1, description="One or more network IDs to attach")
    key_name: Optional[str] = Field(None, description="SSH keypair name for access")
    security_groups: List[str] = Field(default=["default"], description="Security group names")
    user_data: Optional[str] = Field(None, description="Base64-encoded cloud-init user data")
    availability_zone: Optional[str] = Field(None, description="Target availability zone")
    metadata: Optional[Dict[str, str]] = Field(default_factory=dict, description="Arbitrary key-value metadata")

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
    metadata: Dict[str, str] = Field(..., description="Metadata key-value pairs to set/update")

    model_config = {"json_schema_extra": {"example": {"metadata": {"env": "staging", "version": "2.1"}}}}


# ── Response schemas ───────────────────────────────────────────────────────────

class VMResponse(BaseModel):
    id: str
    name: str
    status: VMStatus
    flavor: FlavorSummary
    image: ImageSummary
    networks: Dict[str, List[NetworkAddress]] = Field(default_factory=dict)
    key_name: Optional[str] = None
    security_groups: List[str] = Field(default_factory=list)
    availability_zone: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None
    host: Optional[str] = None
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    power_state: Optional[int] = None
    task_state: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)

    model_config = {"from_attributes": True}


class VMListResponse(BaseModel):
    vms: List[VMResponse]
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
    description: Optional[str] = None
    extra_specs: Dict[str, str] = Field(default_factory=dict)


class FlavorListResponse(BaseModel):
    flavors: List[FlavorResponse]
    total: int


class ImageResponse(BaseModel):
    id: str
    name: str
    status: str
    size_bytes: Optional[int] = None
    min_disk_gb: int = 0
    min_ram_mb: int = 0
    disk_format: Optional[str] = None
    container_format: Optional[str] = None
    visibility: str = "public"
    created_at: datetime
    updated_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)


class ImageListResponse(BaseModel):
    images: List[ImageResponse]
    total: int


class ErrorResponse(BaseModel):
    error: str
    message: str
    request_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str
