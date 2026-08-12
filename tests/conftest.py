from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ts26040_app.config import ReferencePaths
from ts26040_app.references import ReferenceRepository


def write_csv(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


@pytest.fixture()
def reference_repository(tmp_path: Path) -> ReferenceRepository:
    step2 = tmp_path / "step2.csv"
    write_csv(
        step2,
        ["fee_name_ko", "fee_name_en", "procedure_group", "data_variable", "fee"],
        [
            ["헤모글로빈 A1c", "Hemoglobin A1c", "당뇨·내분비검사", "HbA1c", 3440],
            ["트리글리세라이드", "Triglyceride", "지질검사", "Triglyceride; TG", 3550],
            ["표준 12유도 심전도", "Standard 12-lead ECG", "심혈관 기능검사", "ECG; Electrocardiogram", 8560],
        ],
    )

    step3 = tmp_path / "step3.csv"
    write_csv(
        step3,
        ["institute_size", "institute_size_weigth"],
        [
            ["clinic_small-micro", "15%"],
            ["hospital_small-medium", "20%"],
            ["general-hospital_mid-tier", "25%"],
            ["teritary-hospital_large", "30%"],
        ],
    )

    step4 = tmp_path / "step4.csv"
    write_csv(
        step4,
        ["institute_size_examination", "examination_fee"],
        [
            ["clinic_small-micro", 16970],
            ["hospital_small-medium", 16610],
            ["general-hospital_mid-tier", 18280],
            ["teritary-hospital_large", 21150],
        ],
    )

    step5 = tmp_path / "step5.csv"
    write_csv(
        step5,
        ["data_management_cost", "data_management_weigth"],
        [["management_factor", "17%"]],
    )

    step6 = tmp_path / "step6.csv"
    write_csv(
        step6,
        [
            "ranking",
            "icd3",
            "disease_name",
            "patient_count",
            "morbidity_pct",
            "morbidity_group",
            "scarcity_weight_pct",
        ],
        [[1, "E11", "Type 2 diabetes mellitus", 1000, 1.2, "Group 1", -80]],
    )

    step7 = tmp_path / "step7.csv"
    write_csv(
        step7,
        [
            "component_code",
            "component_detail",
            "research_score",
            "clinical_public_health_score",
            "policy_score",
            "industry_ai_score",
            "effectiveness_weight",
        ],
        [
            [1, "Demographics", 5, 4, 1, 5, "15%"],
            [2, "Disease & Health States", 5, 5, 2, 4, "16%"],
            [3, "Health Behavior", 4, 4, 2, 4, "14%"],
            [4, "Oral Disease & Oral Health States", 4, 4, 3, 4, "15%"],
            [5, "Oral Behavior", 3, 3, 2, 3, "11%"],
            [6, "Occupational health", 4, 3, 2, 3, "12%"],
            [7, "Health & Dental Service & Factor", 4, 4, 2, 4, "14%"],
            [8, "Maternal & Infant health", 5, 5, 3, 4, "17%"],
            [9, "Examination & Laboratory", 5, 5, 5, 5, "20%"],
            [10, "Dietary behavior", 4, 4, 3, 4, "15%"],
            [11, "Nutrition intake", 5, 5, 4, 5, "19%"],
            [12, "Food intake", 4, 4, 3, 4, "15%"],
        ],
    )

    paths = ReferencePaths(
        step2=step2,
        step3=step3,
        step4=step4,
        step5=step5,
        step6=step6,
        step7=step7,
    )
    return ReferenceRepository(paths=paths)
