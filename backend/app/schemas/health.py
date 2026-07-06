"""Pydantic response models for the health-check endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str


class DBHealthResponse(BaseModel):
    status: str
    database: str
