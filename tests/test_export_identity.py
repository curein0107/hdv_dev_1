from __future__ import annotations

import json

import pandas as pd

from ts26040_app.exports import build_json_bytes
from ts26040_app.identity import ServiceIdentity
from ts26040_app.models import DatasetInfo


def test_json_export_contains_service_governance_metadata():
    identity = ServiceIdentity(
        operator_name="검증기관",
        operator_unit="가치평가센터",
        methodology_owner="프로파일 위원회",
        methodology_basis="ISO/TS 26040 개발 프레임워크 기반",
        assurance_status="연구·검증용 베타",
        assurance_note="공식 인증이 아님",
        reference_sources=("Source A",),
        data_handling_note="메타정보만 처리",
        contact_email="service@example.org",
        copyright_holder="검증기관",
    )
    payload = json.loads(
        build_json_bytes(
            DatasetInfo(
                dataset_name="Demo",
                evaluation_year=2025,
                institute_code="clinic_small-micro",
                case_count=10,
            ),
            pd.DataFrame([{"variable_name": "Age", "value": 1.0}]),
            {
                "total_value_krw": 1.0,
                "variable_count": 1,
                "total_usable_count": 10,
                "average_effectiveness_pct": 15.0,
                "component_summary": pd.DataFrame(),
                "top5": pd.DataFrame(),
            },
            [],
            identity=identity,
        ).decode("utf-8")
    )

    assert payload["service"]["operator_name"] == "검증기관"
    assert payload["service"]["assurance_status"] == "연구·검증용 베타"
    assert payload["service"]["assurance_note"] == "공식 인증이 아님"
    assert payload["dataset"]["quality_mode"] == "simple"
