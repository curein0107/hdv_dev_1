from __future__ import annotations

import json
from pathlib import Path

from ts26040_app.identity import load_service_identity


def test_service_identity_loads_repository_values(tmp_path: Path):
    path = tmp_path / "service_identity.json"
    path.write_text(
        json.dumps(
            {
                "operator_name": "검증기관",
                "operator_unit": "가치평가센터",
                "methodology_owner": "프로파일 위원회",
                "methodology_basis": "검증 프레임워크",
                "assurance_status": "시험운영",
                "assurance_note": "공식 인증이 아님",
                "reference_sources": ["Source A", "Source B"],
                "data_handling_note": "메타정보만 처리",
                "contact_email": "service@example.org",
                "copyright_holder": "검증기관",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    identity = load_service_identity(path=path)

    assert identity.operator_name == "검증기관"
    assert identity.operator_unit == "가치평가센터"
    assert identity.reference_sources == ("Source A", "Source B")
    assert identity.contact_email == "service@example.org"


def test_service_identity_secrets_override_ignores_empty_values(tmp_path: Path):
    path = tmp_path / "service_identity.json"
    path.write_text(
        json.dumps(
            {
                "operator_name": "기본기관",
                "operator_unit": "기본부서",
                "reference_sources": ["Source A"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    identity = load_service_identity(
        overrides={
            "operator_name": "배포기관",
            "operator_unit": "",
            "contact_email": "contact@example.org",
        },
        path=path,
    )

    assert identity.operator_name == "배포기관"
    assert identity.operator_unit == "기본부서"
    assert identity.contact_email == "contact@example.org"
