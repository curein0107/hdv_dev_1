from __future__ import annotations

import json
from pathlib import Path

from ts26040_app.config import APP_TITLE, REFERENCE_PATHS


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_portal_has_modality_neutral_home_and_profile_branching():
    source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

    assert APP_TITLE == "헬스 데이터 가치 평가 서비스"
    assert "def render_service_type_page" in source
    assert "def render_unstructured_page" in source
    assert "select_mode(STRUCTURED_MODE, INPUT_PAGE)" in source
    assert "select_mode(UNSTRUCTURED_MODE, UNSTRUCTURED_PAGE)" in source
    assert "render_footer(service_identity)" in source
    assert "헬스 데이터 가치평가란?" in source
    assert 'st.button("서비스 시작"' in source
    assert 'st.button("가이드 보기"' in source
    assert "가치평가 서비스 들어가기" not in source


def test_step2_reference_uses_single_fee_column():
    assert REFERENCE_PATHS.step2.name == "step2_medical_unit_fee.csv"
    source = (PROJECT_ROOT / "data" / REFERENCE_PATHS.step2.name).read_text(
        encoding="utf-8-sig"
    )
    header = source.splitlines()[0]
    assert header == "fee_name_ko,fee_name_en,procedure_group,data_variable,fee"
    assert "hospital_base_before_addon_krw" not in header


def test_brand_assets_use_flat_non_ai_visual_language():
    css = (PROJECT_ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    logo = (PROJECT_ROOT / "assets" / "logo.svg").read_text(encoding="utf-8")

    assert "linear-gradient" not in css
    assert "conic-gradient" not in css
    assert "linearGradient" not in logo
    assert "정형 데이터의 수평선과 비정형 데이터의 곡선" in logo
    assert "service-footer" in css
    assert "identity-strip" in css


def test_default_service_identity_declares_assurance_limits():
    payload = json.loads(
        (PROJECT_ROOT / "data" / "service_identity.json").read_text(encoding="utf-8")
    )

    assert payload["operator_name"]
    assert payload["assurance_status"] == "연구·검증용 베타"
    assert "공식 인증·보증하는 것은 아닙니다" in payload["assurance_note"]
    assert payload["copyright_holder"]
