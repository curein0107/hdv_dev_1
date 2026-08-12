from __future__ import annotations

import pandas as pd
import pytest

from ts26040_app.config import METADATA_COLUMNS, QUALITY_MODE_DETAILED
from ts26040_app.models import DatasetInfo
from ts26040_app.references import ReferenceRepository
from ts26040_app.valuation import (
    ValuationEngine,
    normalize_metadata_dataframe,
    summarize_results,
)


def test_supplement_table_2_regression(reference_repository):
    rows = []
    for index in range(30):
        rows.append(
            {
                "variable_name": "region" if index == 0 else f"demo_{index}",
                "variable_description": "City/province" if index == 0 else "Dummy",
                "component_detail": "Demographics",
                "total_count": 6265,
                "usable_count": 6265 if index == 0 else 0,
                "disease_icd3": "",
                "medical_fee_item": "",
                "manual_unit_price_krw": 0,
            }
        )

    # 208 examination variables reproduce the Step 4 allocation 16,970 / 208.
    for index in range(207):
        rows.append(
            {
                "variable_name": f"exam_dummy_{index}",
                "variable_description": "Dummy examination",
                "component_detail": "Examination & Laboratory",
                "total_count": 6265,
                "usable_count": 0,
                "disease_icd3": "",
                "medical_fee_item": "",
                "manual_unit_price_krw": 935,
            }
        )
    rows.append(
        {
            "variable_name": "HE_HbA1c",
            "variable_description": "Glycated hemoglobin",
            "component_detail": "Examination & Laboratory",
            "total_count": 6265,
            "usable_count": 5545,
            "disease_icd3": "E11",
            "medical_fee_item": "",
            "manual_unit_price_krw": 3440,
        }
    )

    engine = ValuationEngine(reference_repository)
    output = engine.calculate(
        pd.DataFrame(rows),
        DatasetInfo(
            dataset_name="KNHANES 2022 regression",
            evaluation_year=2025,
            institute_code="clinic_small-micro",
            case_count=6265,
        ),
    )
    result = pd.DataFrame(output.rows).set_index("variable_name")

    assert result.loc["region", "step2_unit_price_krw"] == pytest.approx(187.0)
    assert result.loc["region", "step3_value_krw"] == pytest.approx(215.05)
    assert result.loc["region", "step5_value_krw"] == pytest.approx(251.6085)
    assert result.loc["region", "step7_unit_value_krw"] == pytest.approx(289.349775)
    assert result.loc["region", "final_variable_value_krw"] == pytest.approx(1812776.340375)

    assert result.loc["HE_HbA1c", "step2_unit_price_krw"] == pytest.approx(3440.0)
    assert result.loc["HE_HbA1c", "step4_value_krw"] == pytest.approx(4037.586538461538)
    assert result.loc["HE_HbA1c", "step5_value_krw"] == pytest.approx(4723.97625)
    assert result.loc["HE_HbA1c", "step6_value_krw"] == pytest.approx(944.79525)
    assert result.loc["HE_HbA1c", "step7_unit_value_krw"] == pytest.approx(1133.7543)
    assert result.loc["HE_HbA1c", "final_variable_value_krw"] == pytest.approx(6286667.5935)


def test_detailed_step1_quality_formulas(reference_repository):
    source = pd.DataFrame(
        [
            {
                "variable_name": "Age",
                "variable_description": "나이",
                "component_detail": "Demographics",
                "total_count": 100,
                "non_empty_count": 90,
                "accurate_count": 81,
                "rule_compliant_count": 72,
                "usable_count": 80,
                "not_used_count": 20,
                "missing_count": 10,
                "disease_icd3": "",
                "medical_fee_item": "",
                "manual_unit_price_krw": 0,
            }
        ]
    )
    output = ValuationEngine(reference_repository).calculate(
        source,
        DatasetInfo(
            dataset_name="quality",
            evaluation_year=2025,
            institute_code="clinic_small-micro",
            case_count=100,
            quality_mode=QUALITY_MODE_DETAILED,
        ),
    )
    row = output.rows[0]
    assert row["step1_accuracy_pct"] == pytest.approx(90.0)
    assert row["step1_completeness_pct"] == pytest.approx(80.0)
    assert row["step1_consistency_pct"] == pytest.approx(80.0)


def test_korean_header_normalization():
    source = pd.DataFrame(
        {
            "변수명": ["Age"],
            "변수 설명": ["나이"],
            "변수 특성": ["Demographics"],
            "전체 케이스 수": [1000],
            "사용 가능 데이터 수": [990],
            "연관 질병 코드": [""],
            "수가코드": [""],
            "직접입력 수가": [0],
        }
    )
    normalized = normalize_metadata_dataframe(source)
    assert list(normalized.columns) == METADATA_COLUMNS
    assert normalized.loc[0, "usable_count"] == 990
    assert normalized.loc[0, "not_used_count"] == 10
    assert normalized.loc[0, "medical_fee_item"] == ""


def test_production_demo_chain_total():
    metadata = pd.DataFrame(
        [
            {"variable_name": "Sex", "variable_description": "성별", "component_detail": "Demographics", "total_count": 1000, "usable_count": 1000, "disease_icd3": "", "medical_fee_item": "", "manual_unit_price_krw": 0},
            {"variable_name": "Age", "variable_description": "나이", "component_detail": "Demographics", "total_count": 1000, "usable_count": 1000, "disease_icd3": "", "medical_fee_item": "", "manual_unit_price_krw": 0},
            {"variable_name": "Smoking", "variable_description": "흡연 여부", "component_detail": "Health Behavior", "total_count": 1000, "usable_count": 850, "disease_icd3": "", "medical_fee_item": "", "manual_unit_price_krw": 0},
            {"variable_name": "TG", "variable_description": "중성지방", "component_detail": "Examination & Laboratory", "total_count": 1000, "usable_count": 700, "disease_icd3": "E78", "medical_fee_item": "트리글리세라이드", "manual_unit_price_krw": 0},
            {"variable_name": "HbA1c", "variable_description": "당화혈색소", "component_detail": "Examination & Laboratory", "total_count": 1000, "usable_count": 1000, "disease_icd3": "E11", "medical_fee_item": "헤모글로빈 A1c", "manual_unit_price_krw": 0},
        ]
    )
    output = ValuationEngine(ReferenceRepository()).calculate(
        metadata,
        DatasetInfo(
            dataset_name="당뇨병 정형 임상 데이터셋",
            evaluation_year=2025,
            institute_code="general-hospital_mid-tier",
            case_count=1000,
        ),
    )
    summary = summarize_results(pd.DataFrame(output.rows))

    assert summary["variable_count"] == 5
    assert summary["total_usable_count"] == 4550
    assert summary["average_completeness_pct"] == pytest.approx(91.0)
    assert summary["total_value_krw"] == pytest.approx(25455441.375)
