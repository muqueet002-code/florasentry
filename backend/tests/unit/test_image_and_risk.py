"""Image validation, risk-engine determinism and confidence-gate tests (Phase 2 + 3).

No database and no network: these prove the pure logic in isolation.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

import pytest
from PIL import Image

from app.ai.preprocessing import softmax, validate_and_prepare
from app.core.errors import ValidationError
from app.integrations.weather.interface import WeatherReading
from app.risk.context import AiSignal, NearbyHistory, RiskContext
from app.risk.rule_engine import RuleBasedRiskEngine, load_ruleset
from app.services.weather_service import WeatherSnapshot


def make_image(
    width: int = 400, height: int = 300, fmt: str = "JPEG", colour: str = "green"
) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=colour).save(buffer, format=fmt)
    return buffer.getvalue()


class TestImageValidation:
    def test_valid_jpeg_is_accepted_and_normalised(self) -> None:
        result = validate_and_prepare(make_image(), "image/jpeg")
        assert result.mime_type == "image/jpeg"
        assert result.width > 0 and result.height > 0
        assert result.thumbnail, "a thumbnail must always be produced"
        assert "blur_score" in result.quality_flags

    def test_png_is_accepted_and_re_encoded_to_jpeg(self) -> None:
        """Re-encoding strips metadata and any embedded payload."""
        result = validate_and_prepare(make_image(fmt="PNG"), "image/png")
        assert result.mime_type == "image/jpeg"

    def test_non_image_bytes_are_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_and_prepare(b"this is definitely not an image", "image/jpeg")
        assert exc.value.code == "IMAGE_INVALID"

    def test_empty_upload_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_and_prepare(b"", "image/jpeg")

    def test_declared_mime_is_not_trusted(self) -> None:
        """A text file claiming to be a JPEG is still rejected."""
        with pytest.raises(ValidationError):
            validate_and_prepare(b"GIF89a-not-really", "image/jpeg")

    def test_tiny_image_is_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_and_prepare(make_image(10, 10), "image/jpeg")
        assert "small" in exc.value.message_key

    def test_oversized_payload_is_rejected(self, monkeypatch) -> None:
        from app.ai import preprocessing

        monkeypatch.setattr(preprocessing.settings, "IMAGE_MAX_BYTES", 100)
        with pytest.raises(ValidationError) as exc:
            validate_and_prepare(make_image(), "image/jpeg")
        assert exc.value.code == "IMAGE_TOO_LARGE"

    def test_dark_image_is_flagged_not_rejected(self) -> None:
        """Quality problems are a signal for the expert, never a hard failure."""
        result = validate_and_prepare(make_image(colour="black"), "image/jpeg")
        assert result.quality_flags["too_dark"] is True


class TestSoftmax:
    def test_normalises_logits(self) -> None:
        probabilities = softmax([2.0, 1.0, 0.1])
        assert abs(sum(probabilities) - 1.0) < 1e-9
        assert probabilities[0] > probabilities[1] > probabilities[2]

    def test_empty_input(self) -> None:
        assert softmax([]) == []


# ---- risk engine -------------------------------------------------------------


def build_context(
    *,
    confidence: float = 0.9,
    low_confidence: bool = False,
    with_ai: bool = True,
    weather_available: bool = True,
    weather_stale: bool = False,
    humidity: float | None = 88.0,
    temperature: float | None = 26.0,
    stage: str | None = "FLOWERING",
    confirmed_nearby: int = 0,
    total_nearby: int = 0,
) -> RiskContext:
    missing: list[dict[str, str]] = []
    signal = None
    if with_ai:
        signal = AiSignal(
            predicted_class="TEST_AGENT",
            confidence=confidence,
            is_low_confidence=low_confidence,
            agent_id=None,
            model_version="test-model-v0",
        )
    else:
        missing.append({"factor": "AI_SIGNAL", "reason": "NO_PREDICTION"})

    if weather_available:
        snapshot = WeatherSnapshot(
            available=True,
            is_stale=weather_stale,
            provider="test",
            reading=WeatherReading(
                observed_at=datetime(2026, 9, 5, tzinfo=UTC),
                temperature_c=temperature,
                humidity_pct=humidity,
                rainfall_mm=1.0,
            ),
            forecast=[],
            fetched_at=datetime(2026, 9, 5, tzinfo=UTC),
        )
    else:
        snapshot = WeatherSnapshot(
            available=False,
            is_stale=False,
            provider="test",
            unavailable_reason="provider down",
        )
        missing.append({"factor": "WEATHER", "reason": "provider down"})

    if stage is None:
        missing.append({"factor": "GROWTH_STAGE", "reason": "NOT_PROVIDED"})

    return RiskContext(
        observation_id=None,
        field_id=None,
        latitude=19.75,
        longitude=75.71,
        observed_at=datetime(2026, 9, 5, tzinfo=UTC),
        ai_signal=signal,
        crop_code="COTTON",
        growth_stage_code=stage,
        weather=snapshot,
        nearby=NearbyHistory(
            confirmed_count=confirmed_nearby,
            predicted_count=0,
            total_count=total_nearby,
            radius_m=5000,
            window_days=30,
        ),
        missing=missing,
    )


class TestRiskEngineDeterminism:
    def test_same_context_gives_identical_result(self) -> None:
        """Determinism is what makes the score testable and explainable."""
        engine = RuleBasedRiskEngine()
        first = engine.evaluate(build_context())
        second = engine.evaluate(build_context())
        assert first.risk_score == second.risk_score
        assert first.risk_level == second.risk_level
        assert first.as_factor_dicts() == second.as_factor_dicts()

    def test_repeated_evaluation_is_stable_across_engine_instances(self) -> None:
        context = build_context()
        scores = {RuleBasedRiskEngine().evaluate(context).risk_score for _ in range(5)}
        assert len(scores) == 1


class TestRiskEngineExplainability:
    def test_contributions_sum_to_the_score(self) -> None:
        """The score is exactly the sum of what it says drove it."""
        result = RuleBasedRiskEngine().evaluate(build_context())
        total = sum(f["contribution"] for f in result.as_factor_dicts())
        assert abs(total - result.risk_score) < 0.05

    def test_every_factor_carries_an_explanation_key(self) -> None:
        result = RuleBasedRiskEngine().evaluate(build_context())
        assert result.contributing_factors
        for factor in result.as_factor_dicts():
            assert factor["explanation_key"].startswith("risk.")

    def test_result_is_labelled_as_prototype_logic(self) -> None:
        result = RuleBasedRiskEngine().evaluate(build_context())
        assert result.disclaimer_key == "risk.prototype_disclaimer"
        assert result.method == "RULE_BASED_V1"
        assert result.ruleset_version

    def test_score_and_level_are_consistent(self) -> None:
        result = RuleBasedRiskEngine().evaluate(build_context())
        bands = load_ruleset()["levels"][result.risk_level]
        assert bands["min"] <= result.risk_score <= bands["max"]


class TestRiskEngineMissingFactors:
    def test_missing_weather_is_reported_not_defaulted(self) -> None:
        result = RuleBasedRiskEngine().evaluate(build_context(weather_available=False))
        missing = {m["factor"] for m in result.missing_factors}
        assert "WEATHER" in missing
        assert "WEATHER" not in {f["factor"] for f in result.as_factor_dicts()}

    def test_missing_inputs_raise_uncertainty(self) -> None:
        complete = RuleBasedRiskEngine().evaluate(build_context())
        degraded = RuleBasedRiskEngine().evaluate(
            build_context(weather_available=False, stage=None, with_ai=False)
        )
        assert degraded.uncertainty > complete.uncertainty

    def test_stale_weather_raises_uncertainty(self) -> None:
        fresh = RuleBasedRiskEngine().evaluate(build_context(weather_stale=False))
        stale = RuleBasedRiskEngine().evaluate(build_context(weather_stale=True))
        assert stale.uncertainty > fresh.uncertainty
        assert stale.weather_is_stale is True

    def test_risk_still_computes_with_no_ai_and_no_weather(self) -> None:
        """Degradation, not failure: remaining factors still produce a score."""
        result = RuleBasedRiskEngine().evaluate(
            build_context(with_ai=False, weather_available=False)
        )
        assert 0 <= result.risk_score <= 100
        assert result.contributing_factors

    def test_renormalisation_means_missing_is_not_treated_as_zero(self) -> None:
        """A dropped factor must not drag the score down as if it scored zero."""
        with_weather = RuleBasedRiskEngine().evaluate(
            build_context(humidity=20.0, temperature=15.0)
        )
        without_weather = RuleBasedRiskEngine().evaluate(build_context(weather_available=False))
        # Removing a LOW-scoring factor should not lower the overall score.
        assert without_weather.risk_score >= with_weather.risk_score


class TestRiskEngineSensitivity:
    def test_nearby_confirmed_cases_increase_risk(self) -> None:
        none_nearby = RuleBasedRiskEngine().evaluate(build_context(confirmed_nearby=0))
        many_nearby = RuleBasedRiskEngine().evaluate(
            build_context(confirmed_nearby=5, total_nearby=6)
        )
        assert many_nearby.risk_score > none_nearby.risk_score

    def test_low_confidence_ai_contributes_less_than_high_confidence(self) -> None:
        """An uncertain model must not drive risk as hard as a confident one."""
        high = RuleBasedRiskEngine().evaluate(build_context(confidence=0.9, low_confidence=False))
        low = RuleBasedRiskEngine().evaluate(build_context(confidence=0.9, low_confidence=True))
        high_ai = next(f for f in high.as_factor_dicts() if f["factor"] == "AI_SIGNAL")
        low_ai = next(f for f in low.as_factor_dicts() if f["factor"] == "AI_SIGNAL")
        assert low_ai["contribution"] < high_ai["contribution"]

    def test_humid_warm_conditions_score_higher_than_dry(self) -> None:
        humid = RuleBasedRiskEngine().evaluate(build_context(humidity=90.0, temperature=26.0))
        dry = RuleBasedRiskEngine().evaluate(build_context(humidity=30.0, temperature=26.0))
        assert humid.risk_score > dry.risk_score
