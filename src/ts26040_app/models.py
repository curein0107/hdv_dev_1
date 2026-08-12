from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .config import QUALITY_MODE_SIMPLE


@dataclass(frozen=True)
class DatasetInfo:
    dataset_name: str
    evaluation_year: int
    institute_code: str
    case_count: int
    quality_mode: str = QUALITY_MODE_SIMPLE


@dataclass(frozen=True)
class FeeLookupResult:
    unit_price_krw: Decimal
    fee_name_ko: str = ""
    fee_name_en: str = ""
    procedure_group: str = ""
    data_variable: str = ""
    source: str = "unmapped"
    matched_query: str = ""
    match_score: Decimal = Decimal("0")
    warning: str = ""


@dataclass(frozen=True)
class ScarcityLookupResult:
    icd3: str = ""
    disease_name: str = ""
    patient_count: int | None = None
    morbidity_pct: Decimal | None = None
    morbidity_group: str = ""
    scarcity_weight_pct: Decimal = Decimal("0")
    warning: str = ""


@dataclass
class CalculationOutput:
    rows: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
