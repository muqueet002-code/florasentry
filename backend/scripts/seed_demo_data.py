"""Seed clearly-marked DEMO_SIMULATION data for an SIH demonstration (Phase 10).

Every observation and field this script creates carries `source_type="DEMO_SIMULATION"`
- the only value this codebase's own comments say a seeder (as opposed to a live
request) is permitted to write (see `app/services/field_service.py` and
`app/services/observation_service.py`). That marks every row as clearly simulated
everywhere the UI shows provenance (`ProvenanceBadge`'s striped fuchsia styling, the
page-level `DemoDataBanner`), and the risk/GIS/hotspot layers already exclude
DEMO_SIMULATION rows from real evidentiary counts by default (`app/risk/context.py`,
`app/gis/hotspots.py`) - this data can never inflate a real farmer's risk score or a
real hotspot.

WHAT THIS SCRIPT DELIBERATELY DOES NOT DO
  - It does not register or fabricate an AI model. This environment's honest state (no
    active model) is preserved; every seeded observation reaches PENDING_REVIEW the
    same way a real one would when `app.ai.inference_service` reports AI_UNAVAILABLE.
  - It does not invent a risk score. Every `RiskAssessment` row here comes from calling
    the real `RuleBasedRiskEngine` (app/risk/rule_engine.py) - the exact same
    deterministic prototype scoring every live observation uses - against a
    synthetic-but-clearly-demo `RiskContext`. The number is genuinely what that engine
    produces for the stated conditions, not an invented statistic. Note: a single
    isolated demo observation cannot honestly reach HIGH risk this way, because the
    nearby-confirmed/local-history factors are computed from REAL corroborating
    reports only (by design - see app/risk/context.py) and a lone demo point has none;
    HIGH requires either a confident AI signal (no model here) or genuine field
    corroboration. This is documented in the Phase 10 report, not worked around.
  - It does not add a new disease/pest. The catalogue's only two seeded agents
    (HEALTHY, UNKNOWN) are Phase 1's provisional vocabulary (TRD decisions D2/D3 are
    still unresolved) - this script uses only those, same as every other test/demo
    path in this codebase.
  - It never hardcodes a password (TRD 37.3, the same rule `create_admin_user.py`
    follows) - it reads DEMO_PASSWORD or prompts interactively.

WHAT IT CREATES (idempotent - safe to re-run; skips if already seeded)
  - Three demo accounts (farmer / extension worker / official) so a demo can switch
    roles without editing the database mid-demonstration.
  - One demo field.
  - A LOW-risk, still-pending-review observation (the "normal" case).
  - A MEDIUM-risk, still-pending-review observation (humid/warm weather driving the
    score up - see the note above on why HIGH is not reachable honestly here).
  - An expert-CORRECTED observation, produced via a real `ReviewService` decision.
    CORRECT (unlike CONFIRM) does not require an existing AI prediction, so it is
    reachable even with no model active.
  - A small cluster of 4 nearby PENDING_REVIEW observations, close enough together to
    form a real hotspot under `app/gis/hotspots.py`'s default radius/min-points.
  - A follow-up on the corrected case, submitted with outcome=WORSENED and linked to
    its own real child observation - the same shape `FollowupService.submit()`
    produces - so the official dashboard's "needing attention" list has something to
    show.

Usage:
    DEMO_PASSWORD=... python scripts/seed_demo_data.py
    python scripts/seed_demo_data.py   # prompts for a password interactively
"""

from __future__ import annotations

import getpass
import os
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import CurrentUser  # noqa: E402
from app.core.rbac import UserRole  # noqa: E402
from app.core.security import hash_password, validate_password_strength  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.integrations.weather.interface import WeatherReading  # noqa: E402
from app.models.catalog import Crop, DiseasePestCatalog  # noqa: E402
from app.models.farmer import Farmer, Field  # noqa: E402
from app.models.followup import Followup  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.risk import RiskAssessment  # noqa: E402
from app.repositories.field_repository import FieldRepository  # noqa: E402
from app.repositories.observation_repository import ObservationRepository  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402
from app.risk.context import NearbyHistory, RiskContext  # noqa: E402
from app.risk.rule_engine import RuleBasedRiskEngine  # noqa: E402
from app.schemas.review import ReviewDecision  # noqa: E402
from app.services.review_service import ReviewService  # noqa: E402
from app.services.weather_service import WeatherSnapshot  # noqa: E402

FARMER_PHONE = "+911000000001"
EXPERT_PHONE = "+911000000002"
OFFICIAL_PHONE = "+911000000003"

# Nashik, Maharashtra - well inside the default operating bbox and unrelated to any
# coordinates used by the automated test suite.
BASE_LAT, BASE_LON = 19.9975, 73.7898
# Small offsets (~tens of metres) so the cluster sits within the default
# HOTSPOT_RADIUS_M (2000m) without leaving the operating bbox.
CLUSTER_OFFSETS = [(0.0, 0.0), (0.0006, 0.0002), (0.0002, 0.0007), (-0.0005, 0.0004)]


def _get_or_create_user(
    db: Session, *, phone: str, full_name: str, role: UserRole, password_hash: str
) -> tuple[object, bool]:
    repo = UserRepository(db)
    existing = repo.get_by_identifier(phone)
    if existing is not None:
        return existing, False
    user = repo.create(full_name=full_name, password_hash=password_hash, role=role, phone=phone)
    if role is UserRole.FARMER:
        db.add(Farmer(user_id=user.id, village="Demo Village", taluka="Demo Taluka"))
        db.flush()
    return user, True


def _current_user(user) -> CurrentUser:
    farmer = db_farmer_for(user)
    return CurrentUser(
        id=user.id,
        role=UserRole(user.role),
        full_name=user.full_name,
        farmer_id=farmer.id if farmer else None,
        district_code=user.district_code,
        preferred_language=user.preferred_language,
    )


def db_farmer_for(user):
    from sqlalchemy.orm import object_session

    session = object_session(user)
    if session is None:
        return None
    return session.execute(select(Farmer).where(Farmer.user_id == user.id)).scalars().first()


def _weather(*, humidity: float, temperature: float, rainfall: float) -> WeatherSnapshot:
    reading = WeatherReading(
        observed_at=datetime.now(UTC),
        temperature_c=temperature,
        humidity_pct=humidity,
        rainfall_mm=rainfall,
        wind_speed_ms=2.5,
        pressure_hpa=1008.0,
    )
    return WeatherSnapshot(
        available=True, is_stale=False, provider="demo_simulation", reading=reading
    )


def _compute_risk(
    *,
    observation: Observation,
    weather: WeatherSnapshot | None,
    nearby: NearbyHistory | None,
) -> RiskAssessment:
    """Real scoring, synthetic-but-labelled inputs - see the module docstring."""
    ctx = RiskContext(
        observation_id=observation.id,
        field_id=observation.field_id,
        latitude=float(observation.latitude),
        longitude=float(observation.longitude),
        observed_at=observation.observed_at,
        weather=weather,
        nearby=nearby,
        missing=[{"factor": "AI_SIGNAL", "reason": "NO_PREDICTION"}],
    )
    result = RuleBasedRiskEngine().evaluate(ctx)
    return RiskAssessment(
        observation_id=observation.id,
        field_id=observation.field_id,
        agent_id=None,
        risk_score=Decimal(str(result.risk_score)),
        risk_level=result.risk_level,
        forecast_period_start=result.forecast_period_start,
        forecast_period_end=result.forecast_period_end,
        contributing_factors=result.as_factor_dicts(),
        missing_factors=result.missing_factors,
        explanation_key=result.explanation_key,
        explanation_params=result.explanation_params,
        uncertainty=Decimal(str(result.uncertainty)),
        method=result.method,
        ruleset_version=result.ruleset_version,
        weather_is_stale=result.weather_is_stale,
    )


def _make_pending_observation(
    repo: ObservationRepository,
    *,
    reported_by: uuid.UUID,
    farmer_id: uuid.UUID,
    field_id: uuid.UUID,
    lat: float,
    lon: float,
    notes: str,
    severity: int | None = None,
) -> Observation:
    # `repo.create()` hardcodes status="PROCESSING" (mirroring the real pipeline's
    # first write); set the terminal COMPLETED status afterward, same as
    # `ObservationService._finalise_status()` does once enrichment is done.
    observation = repo.create(
        farmer_id=farmer_id,
        reported_by=reported_by,
        field_id=field_id,
        crop_id=None,
        variety_id=None,
        growth_stage_id=None,
        observation_type="MANUAL_REPORT",
        latitude=lat,
        longitude=lon,
        gps_accuracy_m=None,
        location_method="MAP_PIN",
        observed_at=datetime.now(UTC),
        reported_severity=severity,
        notes=notes,
        district_code=None,
        source_type="DEMO_SIMULATION",
        verification_status="PENDING_REVIEW",
        processing_errors={
            "ai": {"code": "AI_MODEL_UNAVAILABLE", "reason": "No active model registered"}
        },
    )
    observation.status = "COMPLETED"
    return observation


def main() -> int:
    password = os.environ.get("DEMO_PASSWORD")
    if not password:
        if not sys.stdin.isatty():
            print(
                "ERROR: no DEMO_PASSWORD in the environment and stdin is not a terminal.",
                file=sys.stderr,
            )
            return 2
        password = getpass.getpass("Password for all three demo accounts: ")
        if password != getpass.getpass("Confirm password: "):
            print("ERROR: passwords do not match.", file=sys.stderr)
            return 2
    try:
        validate_password_strength(password)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    with session_scope() as db:
        healthy = (
            db.execute(select(DiseasePestCatalog).where(DiseasePestCatalog.code == "HEALTHY"))
            .scalars()
            .first()
        )
        if healthy is None:
            print(
                "ERROR: reference catalogue is not seeded. "
                "Run scripts/seed_reference_data.py first.",
                file=sys.stderr,
            )
            return 1
        cotton = db.execute(select(Crop).where(Crop.code == "COTTON")).scalars().first()

        pw_hash = hash_password(password)
        farmer_user, farmer_created = _get_or_create_user(
            db,
            phone=FARMER_PHONE,
            full_name="Demo Farmer",
            role=UserRole.FARMER,
            password_hash=pw_hash,
        )
        expert_user, _ = _get_or_create_user(
            db,
            phone=EXPERT_PHONE,
            full_name="Demo Extension Officer",
            role=UserRole.EXTENSION_WORKER,
            password_hash=pw_hash,
        )
        official_user, _ = _get_or_create_user(
            db,
            phone=OFFICIAL_PHONE,
            full_name="Demo Official",
            role=UserRole.OFFICIAL,
            password_hash=pw_hash,
        )
        db.flush()

        if not farmer_created:
            print("Demo accounts already exist; checking for demo observations...")
            existing_field = (
                db.execute(
                    select(Field).where(
                        Field.farmer_id == db_farmer_for(farmer_user).id,
                        Field.source_type == "DEMO_SIMULATION",
                    )
                )
                .scalars()
                .first()
            )
            if existing_field is not None:
                print("Demo data already seeded. Nothing to do.")
                print(f"  Farmer:    {FARMER_PHONE}")
                print(f"  Expert:    {EXPERT_PHONE}")
                print(f"  Official:  {OFFICIAL_PHONE}")
                return 0

        farmer = db_farmer_for(farmer_user)
        field_repo = FieldRepository(db)
        field = field_repo.create(
            farmer_id=farmer.id,
            name="Demo Field (Simulated)",
            centroid=FieldRepository.point_wkt(BASE_LAT, BASE_LON),
            area_ha=Decimal("2.0"),
            soil_type="Black cotton soil",
            irrigation_type="Drip",
            district_code=None,
            current_crop_id=cotton.id if cotton else None,
            current_variety_id=None,
            sowing_date=None,
            created_by=farmer_user.id,
            source_type="DEMO_SIMULATION",
        )

        obs_repo = ObservationRepository(db)

        # --- 1. Normal / low-risk: no corroborating reports, calm dry weather. ---
        low_obs = _make_pending_observation(
            obs_repo,
            reported_by=farmer_user.id,
            farmer_id=farmer.id,
            field_id=field.id,
            lat=BASE_LAT,
            lon=BASE_LON,
            notes="[DEMO] A few small yellow spots on lower leaves, otherwise healthy-looking.",
            severity=1,
        )
        db.add(
            _compute_risk(
                observation=low_obs,
                weather=_weather(humidity=45, temperature=27, rainfall=0),
                nearby=NearbyHistory(
                    confirmed_count=0,
                    predicted_count=0,
                    total_count=0,
                    radius_m=2000,
                    window_days=30,
                ),
            )
        )

        # --- 2. Elevated (MEDIUM) risk: humid/warm weather. See module docstring for
        # why an isolated demo point cannot honestly reach HIGH. ---
        medium_lat, medium_lon = BASE_LAT + 0.02, BASE_LON + 0.02
        medium_obs = _make_pending_observation(
            obs_repo,
            reported_by=farmer_user.id,
            farmer_id=farmer.id,
            field_id=field.id,
            lat=medium_lat,
            lon=medium_lon,
            notes="[DEMO] Leaf spots spreading faster than last week; conditions have been humid.",
            severity=3,
        )
        db.add(
            _compute_risk(
                observation=medium_obs,
                weather=_weather(humidity=88, temperature=28, rainfall=5),
                nearby=NearbyHistory(
                    confirmed_count=0,
                    predicted_count=0,
                    total_count=0,
                    radius_m=2000,
                    window_days=30,
                ),
            )
        )

        # --- 3. Expert-corrected case: a real CORRECT decision (does not require an
        # AI prediction, so it works with no model registered). ---
        corrected_lat, corrected_lon = BASE_LAT - 0.015, BASE_LON - 0.01
        corrected_obs = _make_pending_observation(
            obs_repo,
            reported_by=farmer_user.id,
            farmer_id=farmer.id,
            field_id=field.id,
            lat=corrected_lat,
            lon=corrected_lon,
            notes="[DEMO] Small brown patches, farmer unsure if disease or just sun scorch.",
            severity=2,
        )
        db.add(
            _compute_risk(
                observation=corrected_obs,
                weather=_weather(humidity=60, temperature=30, rainfall=0),
                nearby=NearbyHistory(
                    confirmed_count=0,
                    predicted_count=0,
                    total_count=0,
                    radius_m=2000,
                    window_days=30,
                ),
            )
        )
        db.flush()
        ReviewService(db).decide(
            corrected_obs.id,
            _current_user(expert_user),
            ReviewDecision(
                decision="CORRECT",
                corrected_agent_id=healthy.id,
                note="[DEMO] Examined description and follow-up notes: sun scorch, not disease.",
            ),
        )

        # --- 4. A small cluster -> a real detected hotspot (PostGIS DBSCAN). ---
        cluster_lat, cluster_lon = BASE_LAT + 0.06, BASE_LON - 0.05
        for i, (dlat, dlon) in enumerate(CLUSTER_OFFSETS, start=1):
            cluster_obs = _make_pending_observation(
                obs_repo,
                reported_by=farmer_user.id,
                farmer_id=farmer.id,
                field_id=field.id,
                lat=cluster_lat + dlat,
                lon=cluster_lon + dlon,
                notes=f"[DEMO] Cluster report #{i}: similar leaf discolouration reported nearby.",
                severity=2,
            )
            db.add(
                _compute_risk(
                    observation=cluster_obs,
                    weather=_weather(humidity=70, temperature=29, rainfall=2),
                    nearby=NearbyHistory(
                        confirmed_count=0,
                        predicted_count=0,
                        total_count=0,
                        radius_m=2000,
                        window_days=30,
                    ),
                )
            )

        # --- 5. Follow-up on the corrected case, submitted WORSENED - the same shape
        # FollowupService.submit() produces (a real linked child observation). ---
        db.flush()
        followup_child = _make_pending_observation(
            obs_repo,
            reported_by=farmer_user.id,
            farmer_id=farmer.id,
            field_id=field.id,
            lat=corrected_lat,
            lon=corrected_lon,
            notes="[DEMO] Follow-up: patches have spread to several more leaves since last time.",
            severity=4,
        )
        followup_child.parent_observation_id = corrected_obs.id
        db.add(
            _compute_risk(
                observation=followup_child,
                weather=_weather(humidity=80, temperature=29, rainfall=8),
                nearby=NearbyHistory(
                    confirmed_count=0,
                    predicted_count=0,
                    total_count=0,
                    radius_m=2000,
                    window_days=30,
                ),
            )
        )
        db.flush()
        followup = Followup(
            parent_observation_id=corrected_obs.id,
            followup_observation_id=followup_child.id,
            scheduled_for=datetime.now(UTC),
            status="SUBMITTED",
            outcome="WORSENED",
            notes="[DEMO] Condition has worsened since the expert's assessment.",
            created_by=farmer_user.id,
            submitted_by=farmer_user.id,
            submitted_at=datetime.now(UTC),
        )
        db.add(followup)

        db.flush()
        print("Seeded demo data:")
        print(f"  Field:               {field.id}")
        print(f"  Low-risk case:       {low_obs.id}")
        print(f"  Medium-risk case:    {medium_obs.id}")
        print(f"  Expert-corrected:    {corrected_obs.id} (-> HEALTHY, CORRECTED)")
        print(f"  Hotspot cluster:     4 observations near {cluster_lat:.4f},{cluster_lon:.4f}")
        print(f"  Worsening follow-up: {followup.id} -> {followup_child.id}")
        print()
        print("Demo logins (same password for all three):")
        print(f"  Farmer:    {FARMER_PHONE}")
        print(f"  Expert:    {EXPERT_PHONE}")
        print(f"  Official:  {OFFICIAL_PHONE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
