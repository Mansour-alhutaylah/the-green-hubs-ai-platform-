# CLAUDE.md

# The Green Hubs AI Sustainability Platform

## Project Overview

This repository contains the implementation of an Enterprise AI Sustainability Document Intelligence Platform developed during an 8-week Computer Science internship at The Green Hubs.

The objective is to build a production-oriented Proof of Concept (PoC) that demonstrates enterprise software engineering practices while delivering real business value.

---

# Primary Goal

Build an enterprise-ready AI platform capable of:

- Uploading sustainability documents
- Extracting ESG metrics
- Semantic Search
- RAG
- AI-assisted document analysis
- Executive dashboards
- Structured sustainability data

---

# Existing Reference Project

An existing project named **Hemaya AI Compliance Platform** exists.

Hemaya is a reference implementation only.

Rules:

- Never modify Hemaya.
- Never assume Hemaya code should be copied directly.
- Every imported module must be reviewed first.
- Prefer reuse when architecturally appropriate.
- Refactor when needed.
- Replace only with technical justification.

---

# Architecture Principles

Always follow:

- Clean Architecture
- SOLID Principles
- Separation of Concerns
- Repository Pattern
- Service Layer
- Dependency Injection
- Async Programming
- Modular Design

Avoid:

- Tight Coupling
- God Objects
- Duplicate Logic
- Hardcoded Values

---

# Technology Stack

Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Uvicorn

Database

- PostgreSQL
- Supabase
- pgvector

Authentication

- Supabase Auth
- JWT

AI

- OpenAI API
- LangChain (when appropriate)
- Embeddings
- RAG
- Semantic Search

Frontend

- React
- Vite
- TailwindCSS

Deployment

- Docker
- GitHub Actions

---

# Security Rules

Every implementation must include:

- Input validation
- Authentication
- Authorization
- Secure file upload
- Environment variables
- Secret management
- OWASP Top 10 practices

Never hardcode:

- API Keys
- Passwords
- Secrets
- Tokens

---

# Development Methodology

Use Agile Scrum.

Implement ONE task only.

After every completed task:

Explain:

- What changed
- Why
- Security considerations
- Architecture impact
- Reused Hemaya components

Then STOP.

Wait for approval.

---

# Sprint Workflow

For every Sprint:

1. Explain the objective.
2. Explain available options.
3. Recommend the best approach.
4. Implement one task only.
5. Verify it works.
6. Wait for approval.

Never continue automatically.

---

# Code Review Rules

Before modifying any code:

Determine whether the module should be:

- Keep
- Refactor
- Replace
- Remove

Always explain why.

---

# Coding Standards

Always use:

- Type Hints
- Small Functions
- Meaningful Names
- Docstrings
- Async Programming
- Reusable Components

---

# Documentation

Every task must update documentation when necessary.

Always explain:

- Files created
- Files modified
- Dependencies
- Risks
- Next recommended task

---

# Current Project Status

Phase 0:
Completed ✅

Architecture Assessment:
Completed ✅

Current Sprint:
Sprint 1

Current Focus:

Build the new project foundation.

Do not implement business logic until the architecture is established.

---

# Important Rule

This repository is the source of truth.

Hemaya is only a reference project.

Never migrate code blindly.

Always review, adapt, and improve before integration.