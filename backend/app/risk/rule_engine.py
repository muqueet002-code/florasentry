"""RULE_BASED_V1 risk engine (Phase 3).

Properties this implementation guarantees:

  * DETERMINISTIC - the same RiskContext always produces the same score. No randomness,
    no clock reads inside scoring, no dict-ordering dependence.
  * CONFIGURABLE  - every weight, band and threshold lives in the YAML ruleset.
  * EXPLAINABLE   - contributions sum to the score, so a user can read exactly why the
    score is what it is, and every missing input is listed rather than defaulted.

It is prototype decision-support logic, NOT a validated epidemiological model. Every
result carries `disclaimer_key` saying so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import settings
from app.core.errors import FloraSentryError
from app.risk.context import RiskContext


class RiskUnavailableError(FloraSentryError):
    status_code = 503
    code = "RISK_UNAVAILABLE"
    message = "Risk could not be calculated."
    message_key = "errors.risk_unavailable"
    retriable = True


@dataclass(frozen=True)
class FactorContribution:
    factor: str
    value: Any
    weight: float
    raw_score: float
    contribution: float
    explanation_key: str


@dataclass(frozen=True)
class RiskResult:
    risk_score: float
    risk_level: str
    forecast_period_start: datetime
    forecast_period_end: datetime
    contributing_factors: list[FactorContribution] = field(default_factory=list)
    missing_factors: list[dict[str, str]] = field(default_factory=list)
    explanation_key: str = "risk.summary.low"
    explanation_params: dict[str, Any] = field(default_factory=dict)
    uncertainty: float = 0.0
    method: str = "RULE_BASED_V1"
    ruleset_version: str = "v1.0.0"
    weather_is_stale: bool = False
    disclaimer_key: str = "risk.prototype_disclaimer"

    def as_factor_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                "factor": f.factor,
                "value": f.value,
                "weight": round(f.weight, 4),
                "contribution": round(f.contribution, 2),
                "explanation_key": f.explanation_key,
            }
            for f in self.contributing_factors
        ]


@lru_cache
def load_ruleset(path: str | None = None) -> dict[str, Any]:
    """Load and cache the YAML ruleset. A malformed file fails loudly."""
    ruleset_path = Path(path or settings.RISK_RULESET_PATH)
    if not ruleset_path.is_absolute():
        ruleset_path = Path(__file__).resolve().parents[2] / ruleset_path
    try:
        data = yaml.safe_load(ruleset_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RiskUnavailableError(
            f"Risk ruleset could not be loaded: {type(exc).__name__}"
        ) from exc
    if not isinstance(data, dict) or "factors" not in data:
        raise RiskUnavailableError("Risk ruleset is malformed: no 'factors' section.")
    return data


def _matches(condition: dict[str, Any], values: dict[str, Any]) -> bool:
    """Evaluate one rule's `when` clause against the flattened context values.

    An empty clause matches (the catch-all default rule).
    """
    for key, expected in condition.items():
        # A `foo_in` clause tests the VALUE at `foo`, not at a literal "foo_in" key -
        # look that up before the generic `values.get(key)` below.
        lookup_key = key[: -len("_in")] if key.endswith("_in") else key
        actual = values.get(lookup_key)

        if isinstance(expected, dict):
            if actual is None:
                return False
            if "gte" in expected and not actual >= expected["gte"]:
                return False
            if "gt" in expected and not actual > expected["gt"]:
                return False
            if "lte" in expected and not actual <= expected["lte"]:
                return False
            if "lt" in expected and not actual < expected["lt"]:
                return False
            if "eq" in expected and actual != expected["eq"]:
                return False
            if "between" in expected:
                low, high = expected["between"]
                if not (low <= actual <= high):
                    return False
        elif key.endswith("_in"):
            if actual is None or actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


class RuleBasedRiskEngine:
    """The MVP risk engine. Swappable for an ML engine behind the same call signature."""

    def __init__(self, ruleset: dict[str, Any] | None = None) -> None:
        self.ruleset = ruleset or load_ruleset()

    @property
    def version(self) -> str:
        return str(self.ruleset.get("ruleset_version", "unknown"))

    # ---- context flattening ----

    def _flatten(self, ctx: RiskContext) -> dict[str, Any]:
        """Turn the typed context into the flat values the rules reference."""
        values: dict[str, Any] = {}

        signal = ctx.ai_signal
        values["has_prediction"] = signal is not None
        if signal is not None:
            values["is_low_confidence"] = signal.is_low_confidence
            values["confidence_pct"] = signal.confidence * 100
            # A low-confidence signal is damped: the model is unsure, so the factor
            # should not behave as though it were certain.
            values["confidence_pct_damped"] = signal.confidence * 60

        values["weather_available"] = bool(
            ctx.weather_available and ctx.weather and ctx.weather.reading
        )
        if values["weather_available"] and ctx.weather and ctx.weather.reading:
            reading = ctx.weather.reading
            values["temperature_c"] = reading.temperature_c
            values["humidity_pct"] = reading.humidity_pct
            values["rainfall_mm_recent"] = self._recent_rainfall(ctx)

        values["has_stage"] = ctx.growth_stage_code is not None
        values["stage_code"] = ctx.growth_stage_code

        if ctx.nearby is not None:
            values["nearby_confirmed_count"] = ctx.nearby.confirmed_count
            values["nearby_observation_count"] = ctx.nearby.total_count

        return values

    @staticmethod
    def _recent_rainfall(ctx: RiskContext) -> float | None:
        """Total forecast rainfall over the next few days, plus current precipitation.

        Uses the forecast rather than history because the free provider tier does not
        serve history; the horizon is stated in the explanation.
        """
        if ctx.weather is None:
            return None
        total = 0.0
        seen = False
        if ctx.weather.reading and ctx.weather.reading.rainfall_mm is not None:
            total += float(ctx.weather.reading.rainfall_mm)
            seen = True
        for reading in (ctx.weather.forecast or [])[:3]:
            if reading.rainfall_mm is not None:
                total += float(reading.rainfall_mm)
                seen = True
        return total if seen else None

    # ---- scoring ----

    def evaluate(self, ctx: RiskContext) -> RiskResult:
        values = self._flatten(ctx)
        factors_config = self.ruleset["factors"]

        present: list[FactorContribution] = []
        missing: list[dict[str, str]] = list(ctx.missing)
        missing_names = {m["factor"] for m in missing}

        # Sorted for determinism: dict order must never affect the result.
        for name in sorted(factors_config):
            config = factors_config[name]
            weight = float(config.get("weight", 0))

            # A factor whose required inputs are absent is skipped outright. Letting a
            # catch-all rule score it would assert a value the system does not have.
            unmet = [req for req in config.get("requires", []) if not values.get(req)]
            if unmet:
                factor_name = name.upper()
                if factor_name not in missing_names:
                    missing.append({"factor": factor_name, "reason": "INPUT_UNAVAILABLE"})
                    missing_names.add(factor_name)
                continue

            score, explanation_key = self._score_factor(config, values)

            if score is None:
                factor_name = name.upper()
                if factor_name not in missing_names:
                    missing.append({"factor": factor_name, "reason": "NO_MATCHING_RULE"})
                    missing_names.add(factor_name)
                continue

            present.append(
                FactorContribution(
                    factor=name.upper(),
                    value=self._factor_value(name, values),
                    weight=weight,
                    raw_score=score,
                    contribution=0.0,  # filled after renormalisation
                    explanation_key=explanation_key,
                )
            )

        if not present:
            raise RiskUnavailableError(
                "No risk factor could be evaluated - every input was unavailable."
            )

        # Renormalise across the factors we actually have. Treating a missing factor
        # as zero would assert "no risk from this factor", which is not what we know.
        total_weight = sum(f.weight for f in present) or 1.0
        scored: list[FactorContribution] = []
        raw_total = 0.0
        for f in present:
            normalised_weight = f.weight / total_weight
            contribution = f.raw_score * normalised_weight
            raw_total += contribution
            scored.append(
                FactorContribution(
                    factor=f.factor,
                    value=f.value,
                    weight=normalised_weight,
                    raw_score=f.raw_score,
                    contribution=contribution,
                    explanation_key=f.explanation_key,
                )
            )

        risk_score = round(min(max(raw_total, 0.0), 100.0), 2)
        level = self._level_for(risk_score)
        uncertainty = self._uncertainty(len(missing), ctx.weather_is_stale)

        top = sorted(scored, key=lambda f: f.contribution, reverse=True)[:2]
        start = ctx.observed_at
        end = start + timedelta(days=settings.RISK_FORECAST_DAYS)

        return RiskResult(
            risk_score=risk_score,
            risk_level=level,
            forecast_period_start=start,
            forecast_period_end=end,
            contributing_factors=sorted(scored, key=lambda f: f.contribution, reverse=True),
            missing_factors=missing,
            explanation_key=f"risk.summary.{level.lower()}",
            explanation_params={
                "top_factors": [f.factor for f in top],
                "missing_count": len(missing),
                "forecast_days": settings.RISK_FORECAST_DAYS,
            },
            uncertainty=uncertainty,
            method=str(self.ruleset.get("method", "RULE_BASED_V1")),
            ruleset_version=self.version,
            weather_is_stale=ctx.weather_is_stale,
            disclaimer_key=str(self.ruleset.get("disclaimer_key", "risk.prototype_disclaimer")),
        )

    def _score_factor(
        self, config: dict[str, Any], values: dict[str, Any]
    ) -> tuple[float | None, str]:
        """First matching rule wins. Returns (score, explanation_key)."""
        default_key = str(config.get("explanation_key", "risk.factor.generic"))
        for rule in config.get("rules", []):
            if not _matches(rule.get("when", {}), values):
                continue

            explanation_key = str(rule.get("explanation_key", default_key))
            if "score_expr" in rule:
                expression = rule["score_expr"]
                resolved = values.get(expression)
                if resolved is None:
                    return None, explanation_key
                return float(resolved), explanation_key
            if rule.get("score") is None:
                return None, explanation_key
            return float(rule["score"]), explanation_key
        return None, default_key

    @staticmethod
    def _factor_value(name: str, values: dict[str, Any]) -> Any:
        """The single most informative input for a factor, for the UI to display."""
        mapping = {
            "ai_signal": "confidence_pct",
            "weather": "humidity_pct",
            "growth_stage": "stage_code",
            "nearby_confirmed": "nearby_confirmed_count",
            "local_history": "nearby_observation_count",
        }
        return values.get(mapping.get(name, ""))

    def _level_for(self, score: float) -> str:
        for level, band in self.ruleset["levels"].items():
            if float(band["min"]) <= score <= float(band["max"]):
                return str(level)
        return "HIGH" if score > 66 else "LOW"

    def _uncertainty(self, missing_count: int, weather_stale: bool) -> float:
        config = self.ruleset.get("uncertainty", {})
        value = float(config.get("base", 0.05)) + missing_count * float(
            config.get("per_missing_factor", 0.15)
        )
        if weather_stale:
            value += float(config.get("stale_weather_penalty", 0.1))
        return round(min(value, float(config.get("max", 0.9))), 3)


def utcnow() -> datetime:
    return datetime.now(UTC)
