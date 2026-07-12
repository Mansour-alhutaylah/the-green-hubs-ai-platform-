"""Aggregates all v1 routers. Future entity routers get included here."""

from fastapi import APIRouter

from app.api.v1 import health, organizations

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(organizations.router)
