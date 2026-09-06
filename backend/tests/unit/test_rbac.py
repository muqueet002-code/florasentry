"""RBAC matrix tests (TRD 13.5).

These assert the documented permission table directly, so the TRD table and the running
code cannot drift apart without a test failing.
"""

from __future__ import annotations

import pytest

from app.core.rbac import (
    EXPERT_ROLES,
    Permission,
    UserRole,
    has_permission,
    permissions_for,
    role_matrix,
)


class TestRoleMatrix:
    def test_every_role_is_covered(self) -> None:
        covered = {row["role"] for row in role_matrix()}
        assert covered == {r.value for r in UserRole}

    def test_admin_holds_every_permission(self) -> None:
        assert permissions_for(UserRole.ADMIN) == frozenset(Permission)

    @pytest.mark.parametrize(
        "role,permission",
        [
            (UserRole.FARMER, Permission.CREATE_OBSERVATION),
            (UserRole.FARMER, Permission.MANAGE_OWN_FIELDS),
            (UserRole.FARMER, Permission.SUBMIT_FOLLOWUP),
            (UserRole.EXTENSION_WORKER, Permission.DECIDE_REVIEW),
            (UserRole.EXTENSION_WORKER, Permission.VIEW_HOTSPOTS),
            (UserRole.LAB_EXPERT, Permission.RECORD_LAB_RESULT),
            (UserRole.OFFICIAL, Permission.VIEW_OFFICIAL_DASHBOARD),
        ],
    )
    def test_expected_grants(self, role: UserRole, permission: Permission) -> None:
        assert has_permission(role, permission)

    @pytest.mark.parametrize(
        "role,permission",
        [
            # A farmer must never touch validation, other people's data, or admin.
            (UserRole.FARMER, Permission.DECIDE_REVIEW),
            (UserRole.FARMER, Permission.VIEW_SCOPED_OBSERVATIONS),
            (UserRole.FARMER, Permission.MANAGE_USERS),
            (UserRole.FARMER, Permission.VIEW_OFFICIAL_DASHBOARD),
            (UserRole.FARMER, Permission.READ_AUDIT_LOGS),
            # An official reads aggregates; they never create or validate data.
            (UserRole.OFFICIAL, Permission.CREATE_OBSERVATION),
            (UserRole.OFFICIAL, Permission.DECIDE_REVIEW),
            (UserRole.OFFICIAL, Permission.MANAGE_OWN_FIELDS),
            # A lab expert only sees referred cases, not the whole district.
            (UserRole.LAB_EXPERT, Permission.MANAGE_OWN_FIELDS),
            (UserRole.LAB_EXPERT, Permission.VIEW_OFFICIAL_DASHBOARD),
            # Only an admin administers.
            (UserRole.EXTENSION_WORKER, Permission.MANAGE_USERS),
            (UserRole.EXTENSION_WORKER, Permission.MANAGE_AI_MODELS),
            (UserRole.EXTENSION_WORKER, Permission.MANAGE_DEMO_DATA),
            (UserRole.LAB_EXPERT, Permission.MANAGE_USERS),
            (UserRole.OFFICIAL, Permission.MANAGE_USERS),
        ],
    )
    def test_expected_denials(self, role: UserRole, permission: Permission) -> None:
        assert not has_permission(role, permission)

    def test_only_admin_can_administer(self) -> None:
        admin_only = {
            Permission.MANAGE_USERS,
            Permission.MANAGE_CATALOG,
            Permission.MANAGE_DATA_SOURCES,
            Permission.MANAGE_DEMO_DATA,
            Permission.MANAGE_AI_MODELS,
            Permission.READ_AUDIT_LOGS,
        }
        for role in UserRole:
            if role is UserRole.ADMIN:
                continue
            assert not (permissions_for(role) & admin_only), f"{role} holds an admin permission"

    def test_only_admin_can_seed_demo_data(self) -> None:
        """Demo data must never be creatable by a normal user (TRD 27.2)."""
        holders = [r for r in UserRole if has_permission(r, Permission.MANAGE_DEMO_DATA)]
        assert holders == [UserRole.ADMIN]

    def test_expert_roles_group_is_accurate(self) -> None:
        for role in EXPERT_ROLES:
            assert has_permission(role, Permission.DECIDE_REVIEW)
