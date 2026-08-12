"""Active-source guard: no tenant-owned data is reached without a scope.

MVP Slice 3 moved the tenant predicate out of hand-written service checks
and into the repository SQL. That is only durable if the *next* change
cannot quietly undo it, which is what this guard is for.

It has two halves.

**Structural.** The unsafe shapes must not exist to be called at all.
``IRepository`` declares no ``get``/``list``; no tenant-owned repository
exposes an unscoped read; the two dead generic scaffolds that used to
offer one (``app.services.base.BaseService`` and
``app.infrastructure.repositories.base.SQLAlchemyRepository``) are gone.
Those tests assert absence, so re-adding any of them fails CI rather than
quietly restoring a cross-tenant path.

**Static call analysis.** Every use case (``app/services``) and route
module (``app/api``) is parsed and every repository call inspected:

1. a call to a tenant-scoped repository method must pass
   ``organization_id``;
2. a call to the generic unscoped surface (``get``/``list``/``count``/
   ``update``/``delete``/``get_by_authenticated_id``) without
   ``organization_id`` is a violation unless its exact
   ``(module, receiver, method)`` triple appears in
   :data:`ALLOWED_UNSCOPED_CALL_SITES` -- which currently holds exactly
   two entries, each justified inline.

The previous revision of this guard exempted ``base.py``/``_repository``
wholesale, so *any* call in that module was invisible to rule 2. That
exemption is gone along with the module it protected; exceptions are now
per call site, never per class or per module.

Analysis is on the AST, not text: ``ast`` sees a keyword argument whether
or not it is on the same line, and a method name whether or not a
formatter split it.

Scope: ``app/services`` and ``app/api`` only. Not
``app/infrastructure/repositories`` -- that is where the scoped SQL is
*implemented*, so it legitimately contains the tenant-scoped statements
themselves. Not tests, which construct fixture rows directly on purpose.
"""

import ast
import importlib
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterable, Iterator

import pytest

from app.domain.repositories.base import IRepository
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.domain.repositories.organization import IOrganizationRepository
from app.domain.repositories.user import IUserRepository

REPO_ROOT: Final = Path(__file__).resolve().parents[4]

SCANNED_SOURCE_ROOTS: Final[tuple[str, ...]] = (
    "backend/app/services",
    "backend/app/api",
)

#: Every repository method that reads or writes tenant-owned rows and
#: therefore takes the caller's trusted ``organization_id``. Matched on the
#: *call*, so this stays accurate without importing the interfaces (which
#: would make the guard pass vacuously if a method were renamed on both
#: sides at once).
TENANT_SCOPED_REPOSITORY_METHODS: Final[frozenset[str]] = frozenset(
    {
        # Document
        "get_for_organization",
        "get_by_engagement",
        "update_status",
        "begin_processing",
        "complete_processing",
        "get_read_model_for_organization",
        "list_read_models_for_organization",
        "count_for_organization",
        # Document evidence (MVP Slice 4). Both carry the tenant
        # predicate inside their own SQL; `transition_evidence` carries
        # the expected evidence state and any successor's ownership
        # there too, so a call site that forgot the scope would be
        # writing an evidence decision across a tenant boundary.
        "get_evidence_for_organization",
        "transition_evidence",
        # Engagement
        "update_for_organization",
        # DocumentChunk / ExtractedText
        "get_by_document",
        # DocumentChunkEmbedding
        "claim_new",
        "get_existing",
        "retry_failed",
        "reclaim_stale",
        "mark_completed",
        "mark_failed",
        "search",
        # AnalysisRun
        "claim_or_get",
        "get_by_id",
        "mark_insufficient_evidence",
        "add_citations",
        "get_citations",
    }
)

#: Repository methods that carry no tenant scope in their signature. A call
#: to one of these without ``organization_id`` reads or writes whatever row
#: matches, regardless of owner.
#:
#: ``create`` is deliberately *not* here: it does not read another tenant's
#: data, and ownership on the entity it persists is assigned from trusted
#: server context by the calling service (which additionally rejects a
#: mismatched client-supplied organization -- see ``EngagementService.create``
#: and its integration test).
UNSCOPED_REPOSITORY_METHODS: Final[frozenset[str]] = frozenset(
    {"get", "list", "count", "update", "delete", "get_by_authenticated_id"}
)

#: The complete set of places allowed to call the unscoped surface, keyed
#: ``(module filename, receiver attribute, method)``. Two entries, both
#: narrow, both justified:
#:
#: * ``deps.py`` / ``repository`` / ``get_by_authenticated_id`` -- the
#:   authentication bootstrap. Its argument is the ``sub`` of a JWT whose
#:   signature, issuer and audience ``SupabaseJWTVerifier`` already
#:   validated, so it can only ever return the caller's own profile, and
#:   that profile is what *produces* ``organization_id``. Requiring a scope
#:   here would be circular. See ``IUserRepository``'s module docstring.
#:   A second call site anywhere else fails this guard.
#:
#: * ``organization.py`` / ``_repository`` / ``update`` -- writing the
#:   caller's own organization. ``OrganizationService`` reaches this only
#:   after ``_require_own_organization`` has proven the id equals the
#:   caller's trusted ``organization_id``, and the entity passed carries
#:   that same id. The Organization table is the tenant root, so there is
#:   no second column a predicate could add.
#:
#: Adding a third entry must be a deliberate, reviewed edit.
ALLOWED_UNSCOPED_CALL_SITES: Final[frozenset[tuple[str, str, str]]] = frozenset(
    {
        ("deps.py", "repository", "get_by_authenticated_id"),
        ("organization.py", "_repository", "update"),
    }
)

#: A receiver is treated as a repository handle if it is named exactly
#: ``repository`` (the FastAPI dependency parameter style used in
#: ``deps.py``) or ends with ``_repository`` (the service attribute style).
#: This keeps ordinary Python (``dict.get(...)``) and service-to-service
#: calls (``VectorRetrievalService.search``, which takes ``current_user``
#: and derives the scope itself) out of both rules.
_REPOSITORY_RECEIVER_SUFFIX: Final = "_repository"
_REPOSITORY_RECEIVER_EXACT: Final = "repository"

#: Modules that must no longer be importable: dead generic scaffolds whose
#: only behaviour was unscoped ``get``/``list`` over any model.
REMOVED_GENERIC_SCAFFOLDS: Final[tuple[str, ...]] = (
    "app.services.base",
    "app.infrastructure.repositories.base",
)


@dataclass(frozen=True)
class ScopeViolation:
    path: Path
    line_number: int
    detail: str

    def render(self, root: Path) -> str:
        return f"{self.path.relative_to(root)}:{self.line_number}: {self.detail}"


def _receiver_name(node: ast.Attribute) -> str | None:
    """Return ``_x_repository`` for ``self._x_repository.method(...)``."""

    receiver = node.value
    if isinstance(receiver, ast.Attribute):
        return receiver.attr
    if isinstance(receiver, ast.Name):
        return receiver.id
    return None


def _is_repository_receiver(name: str | None) -> bool:
    if name is None:
        return False
    return name == _REPOSITORY_RECEIVER_EXACT or name.endswith(_REPOSITORY_RECEIVER_SUFFIX)


def find_scope_violations(source: str, path: Path) -> list[ScopeViolation]:
    """Report every unscoped tenant-owned data access in one module."""

    violations: list[ScopeViolation] = []
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue

        receiver = _receiver_name(node.func)
        if not _is_repository_receiver(receiver):
            continue

        method = node.func.attr
        scoped = "organization_id" in {keyword.arg for keyword in node.keywords}
        assert receiver is not None

        if method in TENANT_SCOPED_REPOSITORY_METHODS and not scoped:
            violations.append(
                ScopeViolation(
                    path,
                    node.lineno,
                    f"{receiver}.{method}(...) is tenant-scoped but was called "
                    "without organization_id",
                )
            )
            continue

        if (
            method in UNSCOPED_REPOSITORY_METHODS
            and not scoped
            and (path.name, receiver, method) not in ALLOWED_UNSCOPED_CALL_SITES
        ):
            violations.append(
                ScopeViolation(
                    path,
                    node.lineno,
                    f"{receiver}.{method}(...) carries no organization scope; use a "
                    "tenant-scoped method, or add a justified entry to "
                    "ALLOWED_UNSCOPED_CALL_SITES",
                )
            )

    return violations


def iter_scanned_files(roots: Iterable[Path]) -> Iterator[Path]:
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def _scanned_roots() -> tuple[Path, ...]:
    return tuple(REPO_ROOT / relative for relative in SCANNED_SOURCE_ROOTS)


def scan_for_scope_violations(roots: Iterable[Path]) -> list[ScopeViolation]:
    violations: list[ScopeViolation] = []
    for path in iter_scanned_files(roots):
        violations.extend(find_scope_violations(path.read_text(encoding="utf-8"), path))
    return violations


# ---------------------------------------------------------------------------
# The guard must actually be looking at the real source
# ---------------------------------------------------------------------------


def test_the_guard_resolves_the_real_repository_roots() -> None:
    """A wrong path would make the scan pass vacuously."""

    for root in _scanned_roots():
        assert root.is_dir(), root


def test_the_guard_actually_reads_the_use_cases_it_protects() -> None:
    scanned = {path.name for path in iter_scanned_files(_scanned_roots())}

    assert {
        "document_processing.py",
        "document_upload.py",
        "document_read.py",
        "embedding_generation.py",
        "vector_retrieval.py",
        "rag_analysis.py",
        "engagement.py",
        "organization.py",
        "deps.py",
    } <= scanned


# ---------------------------------------------------------------------------
# Structural: the unsafe shapes do not exist to be called
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["get", "list"])
def test_the_generic_repository_contract_declares_no_unscoped_read(method: str) -> None:
    """``IRepository`` is the base every repository inherits. A generic
    ``get``/``list`` here hands an unscoped read to all of them at once."""

    assert not hasattr(IRepository, method), (
        f"IRepository.{method} reintroduces a generic unscoped read; declare a "
        "tenant-scoped method on the specific interface instead"
    )


@pytest.mark.parametrize("module_name", REMOVED_GENERIC_SCAFFOLDS)
def test_the_dead_generic_scaffolds_stay_deleted(module_name: str) -> None:
    """``BaseService`` and ``SQLAlchemyRepository`` were unreferenced
    scaffolding whose entire surface was unscoped generic ``get``/``list``
    over any model, tenant-owned ones included."""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


@pytest.mark.parametrize(
    "interface,method",
    [
        (IDocumentRepository, "get"),
        (IDocumentRepository, "list"),
        (IEngagementRepository, "get"),
        (IOrganizationRepository, "get"),
        (IOrganizationRepository, "list"),
        (IOrganizationRepository, "count"),
        (IUserRepository, "get"),
        (IUserRepository, "list"),
    ],
)
def test_no_tenant_owned_interface_exposes_an_unscoped_read(
    interface: type, method: str
) -> None:
    """Users cannot be globally listed, organizations cannot be globally
    listed or counted, and documents/engagements cannot be read by bare id
    -- because none of those methods exist, not because nothing calls
    them."""

    assert not hasattr(interface, method), (
        f"{interface.__name__}.{method} is an unscoped tenant-owned access path"
    )


def test_engagement_listing_requires_an_organization() -> None:
    """``list`` is the one surviving list on a tenant-owned interface; its
    scope must be a required parameter, not an optional filter."""

    signature = inspect.signature(IEngagementRepository.list)
    parameter = signature.parameters["organization_id"]

    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_the_user_interface_exposes_exactly_one_read() -> None:
    """The auth bootstrap is the only read, and it is named for that job."""

    reads = {
        name
        for name in dir(IUserRepository)
        if not name.startswith("_") and name not in {"create", "update", "delete"}
    }

    assert reads == {"get_by_authenticated_id"}


# ---------------------------------------------------------------------------
# Static: the real source obeys both rules
# ---------------------------------------------------------------------------


def test_no_use_case_reaches_tenant_owned_data_without_an_organization_scope() -> None:
    violations = scan_for_scope_violations(_scanned_roots())

    assert violations == [], "\n".join(v.render(REPO_ROOT) for v in violations)


def test_every_allowed_unscoped_call_site_still_exists() -> None:
    """An exception that no longer corresponds to real code is dead
    permission -- it must be deleted, not left widening the guard."""

    sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in iter_scanned_files(_scanned_roots())
    }

    for module_name, receiver, method in ALLOWED_UNSCOPED_CALL_SITES:
        assert module_name in sources, f"allowlisted module {module_name} no longer exists"
        assert f".{method}(" in sources[module_name], (
            f"allowlisted call {receiver}.{method}(...) no longer exists in "
            f"{module_name}; remove the exception"
        )


def test_the_allowlist_stays_small() -> None:
    """A growing allowlist is the failure mode this guard exists to catch."""

    assert len(ALLOWED_UNSCOPED_CALL_SITES) == 2


# ---------------------------------------------------------------------------
# The guard detects deliberately unsafe patterns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", sorted(TENANT_SCOPED_REPOSITORY_METHODS))
def test_a_scoped_method_called_without_organization_id_is_detected(
    method: str, tmp_path: Path
) -> None:
    source = f"await self._document_repository.{method}(document_id)\n"

    violations = find_scope_violations(source, tmp_path / "service.py")

    assert len(violations) == 1
    assert "organization_id" in violations[0].detail


@pytest.mark.parametrize("method", sorted(TENANT_SCOPED_REPOSITORY_METHODS))
def test_a_scoped_method_called_with_organization_id_is_accepted(
    method: str, tmp_path: Path
) -> None:
    source = (
        f"await self._document_repository.{method}(\n"
        "    document_id, organization_id=organization_id\n"
        ")\n"
    )

    assert find_scope_violations(source, tmp_path / "service.py") == []


@pytest.mark.parametrize("method", sorted(UNSCOPED_REPOSITORY_METHODS))
def test_the_unscoped_surface_is_detected(method: str, tmp_path: Path) -> None:
    source = f"await self._document_repository.{method}(document_id)\n"

    violations = find_scope_violations(source, tmp_path / "service.py")

    assert len(violations) == 1
    assert "no organization scope" in violations[0].detail


def test_a_tenant_service_cannot_borrow_the_auth_bootstrap(tmp_path: Path) -> None:
    """The bootstrap exception is bound to ``deps.py``. The same call in a
    tenant-facing service is a violation."""

    source = "await self._user_repository.get_by_authenticated_id(some_user_id)\n"

    violations = find_scope_violations(source, tmp_path / "document_read.py")

    assert len(violations) == 1


def test_the_auth_bootstrap_is_allowed_only_at_its_own_call_site(
    tmp_path: Path,
) -> None:
    source = "user = await repository.get_by_authenticated_id(identity)\n"

    assert find_scope_violations(source, tmp_path / "deps.py") == []
    # Same receiver and method, different module -- still rejected.
    assert len(find_scope_violations(source, tmp_path / "documents.py")) == 1


def test_the_organization_update_exception_is_bound_to_its_module(
    tmp_path: Path,
) -> None:
    source = "await self._repository.update(entity)\n"

    assert find_scope_violations(source, tmp_path / "organization.py") == []
    assert len(find_scope_violations(source, tmp_path / "document_read.py")) == 1


def test_a_deps_style_bare_repository_receiver_is_analysed(tmp_path: Path) -> None:
    """``deps.py`` binds repositories to a parameter named ``repository``,
    not ``self._x_repository``. That shape must still be inspected, or the
    whole DI seam would be invisible to this guard."""

    source = "rows = await repository.list(limit=100, offset=0)\n"

    assert len(find_scope_violations(source, tmp_path / "deps.py")) == 1


def test_a_crud_call_that_carries_the_scope_is_accepted(tmp_path: Path) -> None:
    """``IEngagementRepository.list`` requires the scope, so passing it is
    the correct, non-violating shape."""

    source = (
        "await self._repository.list(\n"
        "    organization_id=own_organization_id, limit=page_size, offset=offset\n"
        ")\n"
    )

    assert find_scope_violations(source, tmp_path / "engagement.py") == []


def test_ordinary_python_get_calls_are_not_repository_calls(tmp_path: Path) -> None:
    """`dict.get`/`mapping.get` must never be mistaken for a repository."""

    source = (
        "value = structured_output.get('overall_confidence')\n"
        "message = _SAFE_ERROR_MESSAGES.get(name, 'failed')\n"
        "citation = citation_by_order.get(order)\n"
    )

    assert find_scope_violations(source, tmp_path / "service.py") == []


def test_a_service_to_service_search_is_not_a_repository_call(tmp_path: Path) -> None:
    """``VectorRetrievalService.search`` takes ``current_user`` and derives
    the scope itself, so it must not be judged by the repository rule."""

    source = (
        "await self._vector_retrieval_service.search(\n"
        "    current_user, query=query_text, top_k=top_k\n"
        ")\n"
    )

    assert find_scope_violations(source, tmp_path / "rag_analysis.py") == []


def test_a_violation_split_across_lines_is_still_detected(tmp_path: Path) -> None:
    """Text matching would miss this; the AST does not."""

    source = (
        "await self._document_repository.begin_processing(\n"
        "    document_id,\n"
        ")\n"
    )

    violations = find_scope_violations(source, tmp_path / "service.py")

    assert len(violations) == 1
    assert violations[0].line_number == 1


def test_a_missing_root_is_skipped_rather_than_failing(tmp_path: Path) -> None:
    assert scan_for_scope_violations([tmp_path / "does-not-exist"]) == []
