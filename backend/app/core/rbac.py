"""Role-based access control (TRD 13.5).

The permission matrix lives here as a single source of truth. It is exposed by
`GET /roles` and asserted directly by the RBAC test matrix, so the documented table
and the running code cannot drift apart.

Business logic must never perform its own role checks - it depends on `require_roles`
or `require_permission` from `app.api.deps` instead.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    FARMER = "FARMER"
    EXTENSION_WORKER = "EXTENSION_WORKER"
    LAB_EXPERT = "LAB_EXPERT"
    OFFICIAL = "OFFICIAL"
    ADMIN = "ADMIN"


class Permission(StrEnum):
    """Capability names from the TRD 13.5 matrix.

    Permissions for later-phase modules are declared now so that those modules can be
    added without touching this file. Declaring a permission does NOT mean the feature
    exists - the endpoint enforcing it may still be unimplemented.
    """

    # Profile / self
    MANAGE_OWN_PROFILE = "manage_own_profile"
    # Fields
    MANAGE_OWN_FIELDS = "manage_own_fields"
    VIEW_SCOPED_FIELDS = "view_scoped_fields"
    # Observations
    CREATE_OBSERVATION = "create_observation"
    VIEW_OWN_OBSERVATIONS = "view_own_observations"
    VIEW_SCOPED_OBSERVATIONS = "view_scoped_observations"
    UPLOAD_IMAGE = "upload_image"
    # AI (Phase 2)
    RUN_AI_ANALYZE = "run_ai_analyze"
    MANAGE_AI_MODELS = "manage_ai_models"
    # Expert validation (Phase 5)
    VIEW_REVIEW_QUEUE = "view_review_queue"
    DECIDE_REVIEW = "decide_review"
    REFER_TO_LAB = "refer_to_lab"
    RECORD_LAB_RESULT = "record_lab_result"
    # Advisory (Phase 6)
    REGENERATE_ADVISORY = "regenerate_advisory"
    # Follow-up (Phase 7)
    SUBMIT_FOLLOWUP = "submit_followup"
    ASSESS_FOLLOWUP = "assess_followup"
    # Dashboards / GIS (Phase 4, 8)
    VIEW_OFFICIAL_DASHBOARD = "view_official_dashboard"
    VIEW_HOTSPOTS = "view_hotspots"
    # Administration
    MANAGE_USERS = "manage_users"
    MANAGE_CATALOG = "manage_catalog"
    MANAGE_DATA_SOURCES = "manage_data_sources"
    MANAGE_DEMO_DATA = "manage_demo_data"
    READ_AUDIT_LOGS = "read_audit_logs"


P = Permission
R = UserRole

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    R.FARMER: frozenset(
        {
            P.MANAGE_OWN_PROFILE,
            P.MANAGE_OWN_FIELDS,
            P.CREATE_OBSERVATION,
            P.VIEW_OWN_OBSERVATIONS,
            P.UPLOAD_IMAGE,
            P.SUBMIT_FOLLOWUP,
        }
    ),
    R.EXTENSION_WORKER: frozenset(
        {
            P.MANAGE_OWN_PROFILE,
            P.MANAGE_OWN_FIELDS,
            P.VIEW_SCOPED_FIELDS,
            P.CREATE_OBSERVATION,
            P.VIEW_OWN_OBSERVATIONS,
            P.VIEW_SCOPED_OBSERVATIONS,
            P.UPLOAD_IMAGE,
            P.RUN_AI_ANALYZE,
            P.VIEW_REVIEW_QUEUE,
            P.DECIDE_REVIEW,
            P.REFER_TO_LAB,
            P.REGENERATE_ADVISORY,
            P.SUBMIT_FOLLOWUP,
            P.ASSESS_FOLLOWUP,
            P.VIEW_HOTSPOTS,
        }
    ),
    R.LAB_EXPERT: frozenset(
        {
            P.MANAGE_OWN_PROFILE,
            P.UPLOAD_IMAGE,
            P.RUN_AI_ANALYZE,
            P.VIEW_REVIEW_QUEUE,
            P.DECIDE_REVIEW,
            P.REFER_TO_LAB,
            P.RECORD_LAB_RESULT,
            P.ASSESS_FOLLOWUP,
        }
    ),
    R.OFFICIAL: frozenset(
        {
            P.MANAGE_OWN_PROFILE,
            P.VIEW_SCOPED_OBSERVATIONS,
            P.VIEW_OFFICIAL_DASHBOARD,
            P.VIEW_HOTSPOTS,
        }
    ),
    R.ADMIN: frozenset(Permission),  # unrestricted; every access is audited
}

EXPERT_ROLES = (R.EXTENSION_WORKER, R.LAB_EXPERT)
"""Convenience group. `/expert/*` routes accept either expert role."""


def permissions_for(role: UserRole) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: UserRole, permission: Permission) -> bool:
    return permission in permissions_for(role)


def role_matrix() -> list[dict[str, object]]:
    """Serialisable matrix for `GET /roles`."""
    return [
        {
            "role": role.value,
            "permissions": sorted(p.value for p in permissions_for(role)),
        }
        for role in UserRole
    ]
