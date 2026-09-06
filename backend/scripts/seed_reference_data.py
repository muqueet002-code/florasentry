"""Seed the controlled reference vocabulary (crops, growth stages, agents, symptoms).

Reference data is NOT demo data. It is a real controlled vocabulary the system needs in
order to function, so it is safe to run in every environment. It is idempotent: running
it twice makes no second copy.

The content it loads is PROVISIONAL pending TRD decisions D2 (crop list) and D3 (AI
class list) - see the _README block in app/db/seeds/reference_data.json. Its
`data_sources` row is registered with is_verified = false, so the UI is obliged to
label it as unverified.

Usage:
    python scripts/seed_reference_data.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

# Allow `python scripts/seed_reference_data.py` from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import session_scope  # noqa: E402
from app.models.catalog import (  # noqa: E402
    AgentCrop,
    Crop,
    CropVariety,
    DiseasePestCatalog,
    GrowthStage,
    Symptom,
)
from app.models.provenance import DataSource  # noqa: E402

SEED_FILE = Path(__file__).resolve().parent.parent / "app" / "db" / "seeds" / "reference_data.json"


def _upsert_data_source(db: Session, spec: dict) -> DataSource:
    existing = (
        db.execute(select(DataSource).where(DataSource.code == spec["code"])).scalars().first()
    )
    if existing:
        return existing
    source = DataSource(
        code=spec["code"],
        name=spec["name"],
        source_type=spec["source_type"],
        category=spec["category"],
        provider_name=spec.get("provider_name"),
        url=spec.get("url"),
        licence=spec.get("licence"),
        version_or_release=spec.get("version_or_release"),
        # Never auto-verified: a human must verify a source (TRD 10.2).
        is_verified=False,
        notes=spec.get("notes"),
    )
    db.add(source)
    db.flush()
    return source


def seed(dry_run: bool = False) -> dict[str, int]:
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    counts = {"crops": 0, "growth_stages": 0, "varieties": 0, "agents": 0, "symptoms": 0}

    with session_scope() as db:
        _upsert_data_source(db, data["data_source"])

        crops_by_code: dict[str, Crop] = {}
        for spec in data["crops"]:
            crop = db.execute(select(Crop).where(Crop.code == spec["code"])).scalars().first()
            if crop is None:
                crop = Crop(
                    code=spec["code"],
                    name_en=spec["name_en"],
                    name_hi=spec["name_hi"],
                    name_mr=spec["name_mr"],
                    scientific_name=spec.get("scientific_name"),
                )
                db.add(crop)
                db.flush()
                counts["crops"] += 1
            crops_by_code[crop.code] = crop

            for stage in spec.get("growth_stages", []):
                exists = (
                    db.execute(
                        select(GrowthStage).where(
                            GrowthStage.crop_id == crop.id, GrowthStage.code == stage["code"]
                        )
                    )
                    .scalars()
                    .first()
                )
                if exists is None:
                    db.add(
                        GrowthStage(
                            crop_id=crop.id,
                            code=stage["code"],
                            sequence=stage["sequence"],
                            name_en=stage["name_en"],
                            name_hi=stage["name_hi"],
                            name_mr=stage["name_mr"],
                        )
                    )
                    counts["growth_stages"] += 1

            for variety in spec.get("varieties", []):
                exists = (
                    db.execute(
                        select(CropVariety).where(
                            CropVariety.crop_id == crop.id, CropVariety.code == variety["code"]
                        )
                    )
                    .scalars()
                    .first()
                )
                if exists is None:
                    db.add(
                        CropVariety(
                            crop_id=crop.id,
                            code=variety["code"],
                            name_en=variety["name_en"],
                            name_hi=variety["name_hi"],
                            name_mr=variety["name_mr"],
                            duration_days=variety.get("duration_days"),
                        )
                    )
                    counts["varieties"] += 1

        for spec in data["agents"]:
            agent = (
                db.execute(
                    select(DiseasePestCatalog).where(DiseasePestCatalog.code == spec["code"])
                )
                .scalars()
                .first()
            )
            if agent is None:
                agent = DiseasePestCatalog(
                    code=spec["code"],
                    kind=spec["kind"],
                    name_en=spec["name_en"],
                    name_hi=spec["name_hi"],
                    name_mr=spec["name_mr"],
                    scientific_name=spec.get("scientific_name"),
                    # Phase 1 registers no model, so nothing is AI-supported.
                    # Phase 2 sets this from the model's declared class list.
                    is_ai_supported=False,
                )
                db.add(agent)
                db.flush()
                counts["agents"] += 1

            for crop_code in spec.get("crops", []):
                crop = crops_by_code.get(crop_code)
                if crop is None:
                    continue
                link = (
                    db.execute(
                        select(AgentCrop).where(
                            AgentCrop.agent_id == agent.id, AgentCrop.crop_id == crop.id
                        )
                    )
                    .scalars()
                    .first()
                )
                if link is None:
                    db.add(AgentCrop(agent_id=agent.id, crop_id=crop.id))

        for spec in data.get("symptoms", []):
            exists = (
                db.execute(select(Symptom).where(Symptom.code == spec["code"])).scalars().first()
            )
            if exists is None:
                db.add(
                    Symptom(
                        code=spec["code"],
                        name_en=spec["name_en"],
                        name_hi=spec["name_hi"],
                        name_mr=spec["name_mr"],
                        body_part=spec.get("body_part"),
                    )
                )
                counts["symptoms"] += 1

        if dry_run:
            db.rollback()

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed FloraSentry reference data.")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    counts = seed(dry_run=args.dry_run)
    prefix = "[DRY RUN] would insert" if args.dry_run else "inserted"
    print(f"{prefix}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    print(
        "NOTE: this vocabulary is PROVISIONAL (TRD decisions D2/D3 unresolved) and its "
        "data_sources row is marked is_verified=false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
