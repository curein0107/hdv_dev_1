from __future__ import annotations

import pandas as pd
import streamlit as st

from .config import (
    METADATA_COLUMNS,
    QUALITY_MODE_SIMPLE,
)


HOME_PAGE = "서비스 홈"
SERVICE_TYPE_PAGE = "평가 유형 선택"
INPUT_PAGE = "정형 데이터 입력"
REFERENCE_PAGE = "정형 참조 데이터"
RESULT_PAGE = "정형 평가 결과"
UNSTRUCTURED_PAGE = "비정형 데이터"
ABOUT_PAGE = "운영·검증 정보"

STRUCTURED_MODE = "structured"
UNSTRUCTURED_MODE = "unstructured"

BASE_PAGES = [HOME_PAGE, SERVICE_TYPE_PAGE]
STRUCTURED_PAGES = [INPUT_PAGE, REFERENCE_PAGE, RESULT_PAGE]
UNSTRUCTURED_PAGES = [UNSTRUCTURED_PAGE]
PAGES = BASE_PAGES + STRUCTURED_PAGES + UNSTRUCTURED_PAGES + [ABOUT_PAGE]


def pages_for_mode(mode: str | None) -> list[str]:
    pages = list(BASE_PAGES)
    if mode == STRUCTURED_MODE:
        pages.extend(STRUCTURED_PAGES)
    elif mode == UNSTRUCTURED_MODE:
        pages.extend(UNSTRUCTURED_PAGES)
    pages.append(ABOUT_PAGE)
    return pages


def _row(
    variable_name: str,
    description: str,
    component_detail: str,
    case_count: int,
    usable_count: int,
    disease_icd3: str = "",
    medical_fee_item: str = "",
) -> dict[str, object]:
    return {
        "variable_name": variable_name,
        "variable_description": description,
        "component_detail": component_detail,
        "total_count": case_count,
        "non_empty_count": case_count,
        "accurate_count": case_count,
        "rule_compliant_count": case_count,
        "usable_count": usable_count,
        "not_used_count": max(case_count - usable_count, 0),
        "missing_count": 0,
        "disease_icd3": disease_icd3,
        "medical_fee_item": medical_fee_item,
        "manual_unit_price_krw": 0.0,
    }


def default_metadata(case_count: int = 1000) -> pd.DataFrame:
    rows = [
        _row("Sex", "성별", "Demographics", case_count, case_count),
        _row("Age", "나이", "Demographics", case_count, case_count),
        _row(
            "Smoking",
            "흡연 여부",
            "Health Behavior",
            case_count,
            int(case_count * 0.85),
        ),
        _row(
            "TG",
            "중성지방",
            "Examination & Laboratory",
            case_count,
            int(case_count * 0.70),
            "E78",
            "트리글리세라이드",
        ),
        _row(
            "HbA1c",
            "당화혈색소",
            "Examination & Laboratory",
            case_count,
            case_count,
            "E11",
            "헤모글로빈 A1c",
        ),
    ]
    return pd.DataFrame(rows, columns=METADATA_COLUMNS)


def initialize_state() -> None:
    defaults = {
        "page": HOME_PAGE,
        "data_mode": None,
        "dataset_name": "당뇨병 정형 임상 데이터셋",
        "evaluation_year": 2025,
        "institute_code": "general-hospital_mid-tier",
        "case_count": 1000,
        "quality_mode": QUALITY_MODE_SIMPLE,
        "variables_df": default_metadata(1000),
        "result_df": None,
        "result_summary": None,
        "result_warnings": [],
        "result_dataset_info": None,
        "show_guide": False,
        "uploaded_signature": None,
        "draft_upload_signature": None,
        "last_run_at": None,
        "saved_run_id": None,
        "fee_suggestion_df": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def select_mode(mode: str, destination: str) -> None:
    if mode not in {STRUCTURED_MODE, UNSTRUCTURED_MODE}:
        raise ValueError(f"지원하지 않는 데이터 유형입니다: {mode}")
    st.session_state["data_mode"] = mode
    st.session_state["page"] = destination
    st.rerun()


def navigate(page: str) -> None:
    st.session_state["page"] = page
    st.rerun()
