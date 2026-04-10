"""Images API endpoints."""

from fastapi import APIRouter, Path

from app.schemas.vm import ImageListResponse, ImageResponse
from app.services.openstack_client import openstack_client

router = APIRouter()


@router.get("", response_model=ImageListResponse, summary="List all images")
async def list_images():
    """List all available OS images for VM creation."""
    images = await openstack_client.list_images()
    return ImageListResponse(images=[ImageResponse(**i) for i in images], total=len(images))


@router.get("/{image_id}", response_model=ImageResponse, summary="Get image details")
async def get_image(image_id: str = Path(..., description="Image ID")):
    """Get details of a specific OS image."""
    image = await openstack_client.get_image(image_id)
    return ImageResponse(**image)
