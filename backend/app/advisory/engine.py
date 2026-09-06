"""ADVISORY_RULE_V1 engine (Phase 6).

Turns (agent kind, verification tier) into an ordered list of section KEYS - never
rendered text. The frontend's existing i18n bundles hold the actual wording per
language, exactly like `risk.explanation_key` and `catalog._localised` already do.
Editing `advisory_v1.yaml` changes which sections appear without touching this file.

DETERMINISTIC: the same inputs always produce the same sections. No pesticide names,
doses, application rates or regulatory claims appear anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import settings
from app.core.errors import FloraSentryError
from app.risk.rule_engine import _matches


class AdvisoryUnavailableError(FloraSentryError):
    status_code = 503
    code = "ADVISORY_UNAVAILABLE"
    message = "Advisory could not be generated."
    message_key = "errors.advisory_unavailable"
    retriable = True


@dataclass(frozen=True)
class AdvisorySection:
    key: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdvisoryResult:
    tier: str  # confirmed | ai_unconfirmed | awaiting_review | rejected | unavailable
    sections: list[AdvisorySection]
    method: str
    ruleset_version: str
    disclaimer_key: str
    # True only when the tier is "confirmed" - the one case where the advisory may
    # speak as if the diagnosis were settled rather than provisional.
    is_confirmed: bool


@lru_cache
def load_ruleset(path: str | None = None) -> dict[str, Any]:
    """Load and cache the YAML ruleset. A malformed file fails loudly."""
    ruleset_path = Path(path or settings.ADVISORY_RULESET_PATH)
    if not ruleset_path.is_absolute():
        ruleset_path = Path(__file__).resolve().parents[2] / ruleset_path
    try:
        data = yaml.safe_load(ruleset_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AdvisoryUnavailableError(
            f"Advisory ruleset could not be loaded: {type(exc).__name__}"
        ) from exc
    if not isinstance(data, dict) or "rules" not in data:
        raise AdvisoryUnavailableError("Advisory ruleset is malformed: no 'rules' section.")
    return data


class AdvisoryEngine:
    def __init__(self, ruleset: dict[str, Any] | None = None) -> None:
        self.ruleset = ruleset or load_ruleset()

    @property
    def version(self) -> str:
        return str(self.ruleset.get("ruleset_version", "unknown"))

    def evaluate(
        self,
        *,
        verification_status: str | None,
        agent_kind: str | None,
        risk_level: str | None,
    ) -> AdvisoryResult:
        tiers = self.ruleset.get("tiers", {})
        tier = (
            tiers.get(verification_status, "unavailable") if verification_status else "unavailable"
        )

        values = {"tier": tier, "agent_kind": agent_kind}

        sections: list[str] = []
        for rule in self.ruleset["rules"]:
            if _matches(rule.get("when", {}), values):
                sections = list(rule.get("sections", []))
                break

        params = {"risk_level": risk_level} if risk_level else {}
        section_objs = [
            AdvisorySection(key=f"advisory.section.{s}", params=params) for s in sections
        ]

        return AdvisoryResult(
            tier=tier,
            sections=section_objs,
            method=str(self.ruleset.get("method", "ADVISORY_RULE_V1")),
            ruleset_version=self.version,
            disclaimer_key=str(self.ruleset.get("disclaimer_key", "advisory.prototype_disclaimer")),
            is_confirmed=tier == "confirmed",
        )
