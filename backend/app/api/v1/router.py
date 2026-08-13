"""Aggregates all v1 routers. Future entity routers get included here."""

from fastapi import APIRouter

from app.api.v1 import (
    aios,
    aios_internal,
    analysis,
    auth,
    documents,
    engagements,
    health,
    organizations,
    retrieval,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(organizations.router)
api_v1_router.include_router(engagements.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(retrieval.router)
api_v1_router.include_router(analysis.router)
api_v1_router.include_router(aios.router)
api_v1_router.include_router(aios_internal.router)
