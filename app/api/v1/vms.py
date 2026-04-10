"""VM lifecycle API endpoints."""

from fastapi import APIRouter, Query, Path, status
from typing import Optional

from app.schemas.vm import (
    VMCreateRequest, VMRebootRequest, VMResizeRequest, VMMetadataUpdateRequest,
    VMResponse, VMListResponse, VMActionResponse,
)
from app.services.openstack_client import openstack_client

router = APIRouter()


@router.get("", response_model=VMListResponse, summary="List all VMs")
async def list_vms(
    status: Optional[str] = Query(None, description="Filter by VM status (e.g. ACTIVE, SHUTOFF)"),
    search: Optional[str] = Query(None, description="Filter by name substring"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all VMs with optional filtering and pagination.

    Supports filtering by status and name search.
    """
    result = await openstack_client.list_vms(
        status=status, page=page, page_size=page_size, search=search
    )
    return VMListResponse(**result)


@router.post("", response_model=VMResponse, status_code=status.HTTP_201_CREATED, summary="Create a VM")
async def create_vm(request: VMCreateRequest):
    """
    Create a new VM instance.

    The VM will initially be in **BUILD** state and transition to **ACTIVE** once ready.
    """
    vm = await openstack_client.create_vm(
        name=request.name,
        flavor_id=request.flavor_id,
        image_id=request.image_id,
        network_ids=request.network_ids,
        key_name=request.key_name,
        security_groups=request.security_groups,
        user_data=request.user_data,
        availability_zone=request.availability_zone,
        metadata=request.metadata or {},
    )
    return VMResponse(**vm)


@router.get("/{vm_id}", response_model=VMResponse, summary="Get VM details")
async def get_vm(
    vm_id: str = Path(..., description="VM UUID"),
):
    """Retrieve full details of a specific VM by ID."""
    vm = await openstack_client.get_vm(vm_id)
    return VMResponse(**vm)


@router.post("/{vm_id}/start", response_model=VMActionResponse, summary="Start a VM")
async def start_vm(vm_id: str = Path(..., description="VM UUID")):
    """
    Start a stopped VM.

    Requires the VM to be in **SHUTOFF** or **SUSPENDED** state.
    """
    await openstack_client.start_vm(vm_id)
    return VMActionResponse(
        vm_id=vm_id, action="start", status="accepted",
        message="VM start initiated successfully",
    )


@router.post("/{vm_id}/stop", response_model=VMActionResponse, summary="Stop a VM")
async def stop_vm(vm_id: str = Path(..., description="VM UUID")):
    """
    Stop a running VM (graceful shutdown).

    Requires the VM to be in **ACTIVE** state.
    """
    await openstack_client.stop_vm(vm_id)
    return VMActionResponse(
        vm_id=vm_id, action="stop", status="accepted",
        message="VM stop initiated successfully",
    )


@router.post("/{vm_id}/reboot", response_model=VMActionResponse, summary="Reboot a VM")
async def reboot_vm(
    vm_id: str = Path(..., description="VM UUID"),
    request: VMRebootRequest = VMRebootRequest(),
):
    """
    Reboot a VM.

    - **SOFT** (default): graceful OS-level reboot
    - **HARD**: forced reset (like power cycle)

    Requires VM to be in **ACTIVE** state.
    """
    await openstack_client.reboot_vm(vm_id, request.reboot_type.value)
    return VMActionResponse(
        vm_id=vm_id, action=f"reboot_{request.reboot_type.value.lower()}",
        status="accepted", message=f"{request.reboot_type} reboot initiated",
    )


@router.post("/{vm_id}/resize", response_model=VMActionResponse, summary="Resize a VM")
async def resize_vm(
    vm_id: str = Path(..., description="VM UUID"),
    request: VMResizeRequest = ...,
):
    """
    Resize a VM to a different flavor.

    After resize completes, the VM enters **VERIFY_RESIZE** state.
    Call `/confirm-resize` to accept or `/revert-resize` to roll back.

    Requires VM to be in **ACTIVE** state.
    """
    await openstack_client.resize_vm(vm_id, request.flavor_id)
    return VMActionResponse(
        vm_id=vm_id, action="resize", status="accepted",
        message=f"VM resize to flavor '{request.flavor_id}' initiated. Confirm or revert when ready.",
    )


@router.post("/{vm_id}/confirm-resize", response_model=VMActionResponse, summary="Confirm VM resize")
async def confirm_resize_vm(vm_id: str = Path(..., description="VM UUID")):
    """
    Confirm a pending resize operation.

    Requires VM to be in **VERIFY_RESIZE** state.
    """
    await openstack_client.confirm_resize_vm(vm_id)
    return VMActionResponse(
        vm_id=vm_id, action="confirm_resize", status="accepted",
        message="VM resize confirmed successfully",
    )


@router.patch("/{vm_id}/metadata", response_model=VMResponse, summary="Update VM metadata")
async def update_vm_metadata(
    vm_id: str = Path(..., description="VM UUID"),
    request: VMMetadataUpdateRequest = ...,
):
    """Update or add metadata key-value pairs on a VM."""
    vm = await openstack_client.update_vm_metadata(vm_id, request.metadata)
    return VMResponse(**vm)


@router.delete("/{vm_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a VM")
async def delete_vm(vm_id: str = Path(..., description="VM UUID")):
    """
    Permanently delete a VM.

    This action is **irreversible**. The VM and its ephemeral storage will be removed.
    """
    await openstack_client.delete_vm(vm_id)
