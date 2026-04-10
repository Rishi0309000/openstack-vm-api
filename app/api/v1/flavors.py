"""Flavor and Image API endpoints."""

from fastapi import APIRouter, Path
from app.schemas.vm import FlavorResponse, FlavorListResponse, ImageResponse, ImageListResponse
from app.services.openstack_client import openstack_client

# ── Flavors ────────────────────────────────────────────────────────────────────

router = APIRouter()


@router.get("", response_model=FlavorListResponse, summary="List all flavors")
async def list_flavors():
    """List all available VM flavors (CPU/RAM/disk profiles)."""
    flavors = await openstack_client.list_flavors()
    return FlavorListResponse(flavors=[FlavorResponse(**f) for f in flavors], total=len(flavors))


@router.get("/{flavor_id}", response_model=FlavorResponse, summary="Get flavor details")
async def get_flavor(flavor_id: str = Path(..., description="Flavor ID")):
    """Get details of a specific flavor."""
    flavor = await openstack_client.get_flavor(flavor_id)
    return FlavorResponse(**flavor)
