from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine, select

from .config import LOCAL_DATA_DIR, PROFILE_NAME
from .models import DatasetInfo


def resolve_database_url(secrets: Any | None = None) -> tuple[str, bool]:
    """Return (database_url, is_durable_remote_store)."""
    if secrets is not None:
        try:
            value = secrets.get("database", {}).get("url")
            if value:
                return str(value), not str(value).startswith("sqlite")
        except Exception:
            pass
    environment_value = os.getenv("DATABASE_URL", "").strip()
    if environment_value:
        return environment_value, not environment_value.startswith("sqlite")

    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(LOCAL_DATA_DIR / 'valuation_results.sqlite3').as_posix()}", False


class ResultStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine = create_engine(database_url, pool_pre_ping=True, future=True)
        self.metadata = MetaData()
        self.runs = Table(
            "valuation_runs",
            self.metadata,
            Column("run_id", String(64), primary_key=True),
            Column("dataset_name", String(255), nullable=False),
            Column("evaluation_year", Integer, nullable=False),
            Column("institute_code", String(100), nullable=False),
            Column("case_count", Integer, nullable=False),
            Column("variable_count", Integer, nullable=False),
            Column("total_usable_count", Integer, nullable=False),
            Column("total_value_krw", Float, nullable=False),
            Column("profile_name", String(255), nullable=False),
            Column("payload_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.metadata.create_all(self.engine)

    def save(
        self,
        dataset_info: DatasetInfo,
        result_df: pd.DataFrame,
        summary: dict[str, Any],
        warnings: list[str],
    ) -> str:
        run_id = f"RUN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        payload = {
            "dataset": {
                "dataset_name": dataset_info.dataset_name,
                "evaluation_year": dataset_info.evaluation_year,
                "institute_code": dataset_info.institute_code,
                "case_count": dataset_info.case_count,
                "quality_mode": dataset_info.quality_mode,
            },
            "warnings": warnings,
            "results": result_df.to_dict(orient="records"),
        }
        with self.engine.begin() as connection:
            connection.execute(
                self.runs.insert().values(
                    run_id=run_id,
                    dataset_name=dataset_info.dataset_name,
                    evaluation_year=dataset_info.evaluation_year,
                    institute_code=dataset_info.institute_code,
                    case_count=dataset_info.case_count,
                    variable_count=int(summary["variable_count"]),
                    total_usable_count=int(summary["total_usable_count"]),
                    total_value_krw=float(summary["total_value_krw"]),
                    profile_name=PROFILE_NAME,
                    payload_json=json.dumps(payload, ensure_ascii=False, default=str),
                    created_at=datetime.now(timezone.utc),
                )
            )
        return run_id

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        statement = (
            select(
                self.runs.c.run_id,
                self.runs.c.dataset_name,
                self.runs.c.evaluation_year,
                self.runs.c.variable_count,
                self.runs.c.total_usable_count,
                self.runs.c.total_value_krw,
                self.runs.c.created_at,
            )
            .order_by(self.runs.c.created_at.desc())
            .limit(limit)
        )
        with self.engine.connect() as connection:
            return [dict(row._mapping) for row in connection.execute(statement)]
