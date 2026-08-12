from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"
LOCAL_DATA_DIR = PROJECT_ROOT / "local_data"
SERVICE_IDENTITY_PATH = DATA_DIR / "service_identity.json"


# Public portal identity. The title is intentionally modality-neutral so the
# service can expand from structured records to imaging, text, audio and
# waveform valuation without another rebrand.
APP_TITLE = "헬스 데이터 가치 평가 서비스"
APP_VERSION = "2025.3 · BETA"
STRUCTURED_SERVICE_TITLE = "정형 헬스 데이터 가치 평가"
UNSTRUCTURED_SERVICE_TITLE = "비정형 헬스 데이터 가치 평가"
PROFILE_NAME = "KR-2025 정형 헬스 데이터 가치평가 프로파일"
METHODOLOGY_NAME = "ISO/TS 26040 개발 프레임워크 기반 7-Step 모델"
PROFILE_YEAR = 2025
CURRENCY = "KRW"

# Supplements Table 1/2의 한국 기준 설문·인구학·식이 조사비용.
# 각 Component Survey Group 내 변수 수로 균등 배분한다.
SURVEY_REFERENCE_FEE_KRW = Decimal("5610")

# 숫자 처리 정밀도. 계산 중에는 반올림하지 않고 출력 단계에서만
# 표시 반올림을 수행한다.
DISPLAY_MONEY_DECIMALS = 2

QUALITY_MODE_SIMPLE = "simple"
QUALITY_MODE_DETAILED = "detailed"
QUALITY_MODE_LABELS = {
    QUALITY_MODE_SIMPLE: "간편 입력 — 전체·사용가능 건수 중심",
    QUALITY_MODE_DETAILED: "상세 입력 — 정확성·완전성·일관성 건수 포함",
}

# Upload files contain the historical typo "teritary". Normalize it at the
# application boundary while keeping backward compatibility with saved drafts.
INSTITUTE_CODE_ALIASES = {
    "teritary-hospital_large": "tertiary-hospital_large",
}

INSTITUTE_LABELS = {
    "clinic_small-micro": "의원",
    "hospital_small-medium": "병원",
    "general-hospital_mid-tier": "종합병원",
    "tertiary-hospital_large": "상급종합병원",
}

QUESTIONNAIRE_DETAILS = {
    "Disease & Health States",
    "Health Behavior",
    "Oral Disease & Oral Health States",
    "Oral Behavior",
    "Occupational health",
    "Health & Dental Service & Factor",
    "Maternal & Infant health",
}

DIETARY_DETAILS = {
    "Dietary behavior",
    "Nutrition intake",
    "Food intake",
}

NON_VALUED_COMPONENT = "Weight & Not Used & Etc"

# Canonical metadata schema. The five Step 1 detail-count columns are preserved
# even when the user selects the compact UI. In compact mode they are derived
# deterministically from total_count and usable_count.
METADATA_COLUMNS = [
    "variable_name",
    "variable_description",
    "component_detail",
    "total_count",
    "non_empty_count",
    "accurate_count",
    "rule_compliant_count",
    "usable_count",
    "not_used_count",
    "missing_count",
    "disease_icd3",
    "medical_fee_item",
    "manual_unit_price_krw",
]

SIMPLE_EDITOR_COLUMNS = [
    "variable_name",
    "variable_description",
    "component_detail",
    "total_count",
    "usable_count",
    "disease_icd3",
    "medical_fee_item",
    "manual_unit_price_krw",
]

DETAILED_EDITOR_COLUMNS = [
    "variable_name",
    "variable_description",
    "component_detail",
    "total_count",
    "non_empty_count",
    "accurate_count",
    "rule_compliant_count",
    "not_used_count",
    "missing_count",
    "usable_count",
    "disease_icd3",
    "medical_fee_item",
    "manual_unit_price_krw",
]

METADATA_KOREAN_HEADERS = {
    "variable_name": "변수명",
    "variable_description": "변수 설명",
    "component_detail": "변수 특성",
    "total_count": "전체 케이스 수",
    "non_empty_count": "비어있지 않은 데이터 수",
    "accurate_count": "정확한 데이터 수",
    "rule_compliant_count": "규칙 준수 데이터 수",
    "usable_count": "사용 가능 데이터 수",
    "not_used_count": "미사용 데이터 수",
    "missing_count": "결측 데이터 수",
    "disease_icd3": "연관 질병 코드",
    "medical_fee_item": "Step 2 의료행위",
    "manual_unit_price_krw": "직접입력 수가(KRW)",
}


@dataclass(frozen=True)
class ReferencePaths:
    step2: Path = DATA_DIR / "step2_medical_unit_fee.csv"
    step3: Path = DATA_DIR / "step3_institue_size.csv"
    step4: Path = DATA_DIR / "step4_examination_fee_kr2025.csv"
    step5: Path = DATA_DIR / "step5_data_management_cost.csv"
    step6: Path = DATA_DIR / "step6_disease_scarcity_kr2025.csv"
    step7: Path = DATA_DIR / "step7_component_reference.csv"


REFERENCE_PATHS = ReferencePaths()
