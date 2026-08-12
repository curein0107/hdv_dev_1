from __future__ import annotations

import hashlib
import html
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ts26040_app.auth import require_optional_password
from ts26040_app.config import (
    APP_TITLE,
    DETAILED_EDITOR_COLUMNS,
    INSTITUTE_CODE_ALIASES,
    INSTITUTE_LABELS,
    METADATA_KOREAN_HEADERS,
    PROFILE_NAME,
    QUALITY_MODE_DETAILED,
    QUALITY_MODE_LABELS,
    QUALITY_MODE_SIMPLE,
    SIMPLE_EDITOR_COLUMNS,
    STRUCTURED_SERVICE_TITLE,
    UNSTRUCTURED_SERVICE_TITLE,
)
from ts26040_app.exports import (
    build_csv_bytes,
    build_excel_bytes,
    build_html_report,
    build_json_bytes,
)
from ts26040_app.identity import load_service_identity
from ts26040_app.models import DatasetInfo
from ts26040_app.references import ReferenceRepository
from ts26040_app.state import (
    ABOUT_PAGE,
    HOME_PAGE,
    INPUT_PAGE,
    REFERENCE_PAGE,
    RESULT_PAGE,
    SERVICE_TYPE_PAGE,
    STRUCTURED_MODE,
    UNSTRUCTURED_MODE,
    UNSTRUCTURED_PAGE,
    default_metadata,
    initialize_state,
    select_mode,
)
from ts26040_app.storage import ResultStore, resolve_database_url
from ts26040_app.ui import (
    feature_card,
    guide_content,
    load_css,
    metric_card,
    render_footer,
    render_home_preview,
    render_identity_strip,
    render_sidebar,
    render_top_header,
    section_title,
)
from ts26040_app.valuation import (
    ValuationEngine,
    normalize_metadata_dataframe,
    summarize_results,
    validate_metadata,
)


st.set_page_config(
    page_title=APP_TITLE,
    page_icon=str(PROJECT_ROOT / "assets" / "logo.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
initialize_state()

if not require_optional_password():
    st.stop()


@st.cache_resource(show_spinner="Step 2–7 참조 데이터베이스를 준비하는 중입니다...")
def get_repository() -> ReferenceRepository:
    return ReferenceRepository()


@st.cache_resource(show_spinner=False)
def get_result_store(database_url: str) -> ResultStore:
    return ResultStore(database_url)


repository = get_repository()
engine = ValuationEngine(repository)
database_url, durable_store = resolve_database_url(st.secrets)
store = get_result_store(database_url)
try:
    service_overrides = st.secrets.get("service", {})
except Exception:
    service_overrides = {}
service_identity = load_service_identity(service_overrides)

render_top_header(service_identity)
if st.session_state["page"] != HOME_PAGE:
    render_sidebar(service_identity)


def set_page(page: str) -> None:
    st.session_state["page"] = page
    st.rerun()


def safe_html(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def current_dataset_info() -> DatasetInfo:
    return DatasetInfo(
        dataset_name=str(st.session_state["dataset_name"]).strip(),
        evaluation_year=int(st.session_state["evaluation_year"]),
        institute_code=str(st.session_state["institute_code"]),
        case_count=int(st.session_state["case_count"]),
        quality_mode=str(st.session_state["quality_mode"]),
    )


def _read_csv_payload(payload: bytes) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(payload), encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(f"CSV 인코딩을 해석하지 못했습니다: {last_error}")


def build_input_draft_bytes() -> bytes:
    quality_mode = str(st.session_state["quality_mode"])
    variables = normalize_metadata_dataframe(
        st.session_state["variables_df"],
        int(st.session_state["case_count"]),
        quality_mode,
    )
    payload = {
        "draft_schema": "ts26040-input-draft-v2",
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": {
            "dataset_name": str(st.session_state["dataset_name"]),
            "evaluation_year": int(st.session_state["evaluation_year"]),
            "institute_code": str(st.session_state["institute_code"]),
            "case_count": int(st.session_state["case_count"]),
            "quality_mode": quality_mode,
        },
        "variables": variables.where(pd.notna(variables), None).to_dict(orient="records"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def restore_input_draft(payload: bytes) -> None:
    draft = json.loads(payload.decode("utf-8-sig"))
    if draft.get("draft_schema") not in {
        "ts26040-input-draft-v1",
        "ts26040-input-draft-v2",
    }:
        raise ValueError("지원하지 않는 입력 초안 형식입니다.")

    dataset = draft.get("dataset") or {}
    institute_code = str(dataset.get("institute_code", ""))
    institute_code = INSTITUTE_CODE_ALIASES.get(institute_code, institute_code)
    if institute_code not in INSTITUTE_LABELS:
        raise ValueError("초안의 기관종별 코드가 유효하지 않습니다.")

    quality_mode = str(dataset.get("quality_mode", QUALITY_MODE_SIMPLE))
    if quality_mode not in QUALITY_MODE_LABELS:
        quality_mode = QUALITY_MODE_SIMPLE

    case_count = int(dataset.get("case_count", 0))
    if case_count < 1:
        raise ValueError("초안의 케이스 수가 유효하지 않습니다.")

    st.session_state["dataset_name"] = str(dataset.get("dataset_name", ""))
    st.session_state["evaluation_year"] = int(dataset.get("evaluation_year", 2025))
    st.session_state["institute_code"] = institute_code
    st.session_state["case_count"] = case_count
    st.session_state["quality_mode"] = quality_mode
    st.session_state["variables_df"] = normalize_metadata_dataframe(
        pd.DataFrame(draft.get("variables") or []), case_count, quality_mode
    )


def execute_valuation(navigate_to_results: bool = True) -> bool:
    dataset_info = current_dataset_info()
    if not dataset_info.dataset_name:
        st.error("데이터셋명을 입력하십시오.")
        return False

    variables = normalize_metadata_dataframe(
        st.session_state["variables_df"],
        dataset_info.case_count,
        dataset_info.quality_mode,
    )
    errors, warnings = validate_metadata(
        variables, repository, dataset_info.quality_mode
    )
    if errors:
        st.error("\n".join(f"• {item}" for item in errors))
        return False

    try:
        output = engine.calculate(variables, dataset_info)
    except Exception as exc:
        st.error(f"가치평가 실행 오류: {exc}")
        return False

    result_df = pd.DataFrame(output.rows)
    st.session_state["variables_df"] = variables
    st.session_state["result_df"] = result_df
    st.session_state["result_summary"] = summarize_results(result_df)
    st.session_state["result_warnings"] = sorted(set(warnings + output.warnings))
    st.session_state["result_dataset_info"] = dataset_info
    st.session_state["last_run_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["saved_run_id"] = None

    if navigate_to_results:
        set_page(RESULT_PAGE)
    return True


def render_home() -> None:
    """Context requirement: only Service Start and Guide View are actionable."""
    hero_left, hero_right = st.columns([1.02, 0.98], gap="large")
    with hero_left:
        st.markdown(
            """
            <div class="hero-copy">
              <div class="hero-kicker">HEALTH DATA VALUATION</div>
              <h1>헬스 데이터의 가치를<br>근거와 추적성으로 설명합니다.</h1>
              <p>데이터 생성비용, 생산기관, 관리비, 질병 희소성, 활용 효과성을 결합하여 데이터셋의 모델 기반 순화폐가치를 산정합니다.</p>
              <div class="valuation-intro">
                <b>헬스 데이터 가치평가란?</b>
                <span>의료·연구 데이터의 생성과 관리에 투입된 자원, 대체 가능성, 희소성, 활용 잠재력을 정량화하여 데이터 활용·교환·투자 의사결정의 근거를 만드는 절차입니다.</span>
                <small>산출값은 시장 거래가격, 보험 청구액, 지불의사금액 또는 법정 감정가와 동일하지 않습니다.</small>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        start_col, guide_col = st.columns([1.1, 0.9])
        with start_col:
            if st.button("서비스 시작", type="primary", use_container_width=True):
                set_page(SERVICE_TYPE_PAGE)
        with guide_col:
            if st.button("가이드 보기", use_container_width=True):
                st.session_state["show_guide"] = not st.session_state["show_guide"]
                st.rerun()

    with hero_right:
        render_home_preview()

    render_identity_strip(service_identity)

    if st.session_state["show_guide"]:
        with st.container(border=True):
            guide_content()

    st.markdown('<div class="home-section-gap"></div>', unsafe_allow_html=True)
    section_title(
        "하나의 포털, 데이터 형식별 독립 평가 프로파일",
        "정형과 비정형 데이터의 평가 논리를 분리하되 운영·검증·보고 체계는 공통으로 관리합니다.",
        "SERVICE ARCHITECTURE",
    )
    cols = st.columns(4, gap="medium")
    cards = [
        ("01", "데이터 형식 분리", "정형·비정형을 구분하여 데이터 특성에 맞는 산정모델 적용", "forest"),
        ("02", "근거자료 연결", "Step 2~7 참조 CSV와 Supplement Table 산식 버전 관리", "rust"),
        ("03", "계산 추적성", "각 변수의 Step 1~7 중간값과 적용 근거를 결과에 보존", "slate"),
        ("04", "운영 신뢰성", "운영기관, 방법론 책임, 보증 범위, 저작권을 화면과 보고서에 공개", "sand"),
    ]
    for column, card in zip(cols, cards):
        with column:
            feature_card(*card)

    st.markdown(
        """
        <div class="process-strip">
          <div><b>01</b><span><strong>서비스 진입</strong><small>가치평가 정의와 한계 확인</small></span></div>
          <i>—</i>
          <div><b>02</b><span><strong>정형·비정형 선택</strong><small>데이터 형식별 프로파일 분리</small></span></div>
          <i>—</i>
          <div><b>03</b><span><strong>메타정보 평가</strong><small>참조자료와 내부 계산식 적용</small></span></div>
          <i>—</i>
          <div><b>04</b><span><strong>결과·감사추적</strong><small>보고서, 참조 해시, 저장 기록</small></span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_service_type_page() -> None:
    section_title(
        "평가할 헬스 데이터 형식을 선택하세요",
        "데이터 형식에 따라 생성비용·품질·희소성·활용성의 측정기준이 달라지므로 프로파일을 분리합니다.",
        "SELECT DATA PROFILE",
    )

    structured_col, unstructured_col = st.columns(2, gap="large")
    with structured_col:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="type-card type-card-active">
                  <div class="type-card-status">AVAILABLE · KR-2025</div>
                  <h3>{safe_html(STRUCTURED_SERVICE_TITLE)}</h3>
                  <p>표·레코드 형태의 변수 메타정보를 기반으로 의료행위 수가, 기관 규모, 관리비, 질병 희소성, 활용 효과성을 적용합니다.</p>
                  <ul>
                    <li>국가 건강조사·건강검진 데이터</li>
                    <li>EHR·CDW·마이헬스웨이 정형 변수</li>
                    <li>검사·생체신호·설문·식이 데이터</li>
                  </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "정형 데이터 평가 시작",
                type="primary",
                use_container_width=True,
                key="select_structured",
            ):
                select_mode(STRUCTURED_MODE, INPUT_PAGE)

    with unstructured_col:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="type-card type-card-planned">
                  <div class="type-card-status">ROADMAP · EXTENSIBLE</div>
                  <h3>{safe_html(UNSTRUCTURED_SERVICE_TITLE)}</h3>
                  <p>영상·임상텍스트·음성·파형 데이터의 획득, 주석, 저장, 품질, 개인정보 위험, 모델 활용성을 반영하는 별도 프로파일입니다.</p>
                  <ul>
                    <li>의료영상·병리·안저·내시경</li>
                    <li>임상기록·판독문·상담 음성</li>
                    <li>ECG·EEG·연속 생체신호</li>
                  </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "비정형 평가 확장 설계 보기",
                use_container_width=True,
                key="select_unstructured",
            ):
                select_mode(UNSTRUCTURED_MODE, UNSTRUCTURED_PAGE)

    st.markdown(
        """
        <div class="architecture-note">
          <b>확장 원칙</b>
          <span>공통 로그인·운영·검증·저장·보고 체계는 공유하지만, 정형과 비정형의 산정변수·품질지표·참조 데이터베이스는 독립 버전으로 관리합니다.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_unstructured_page() -> None:
    st.session_state["data_mode"] = UNSTRUCTURED_MODE
    section_title(
        UNSTRUCTURED_SERVICE_TITLE,
        "현재 빌드에서는 확장 구조와 평가축을 제시하며 실제 금액 산정 엔진은 제공하지 않습니다.",
        "UNSTRUCTURED DATA · ROADMAP",
    )

    st.markdown(
        """
        <div class="roadmap-banner">
          <span>개발 상태</span>
          <b>확장 모듈 설계 단계</b>
          <p>정형 데이터 산식을 그대로 재사용하지 않고, 비정형 데이터의 획득·주석·품질·저장·개인정보 위험·AI 활용성을 별도 모델로 설계합니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    modality_cols = st.columns(4, gap="medium")
    modalities = [
        ("01", "의료영상", "DICOM, 병리 WSI, 안저, 내시경", "획득·판독·주석·저장비용"),
        ("02", "임상텍스트", "EMR 노트, 판독문, 퇴원요약", "작성·비식별화·구조화비용"),
        ("03", "음성·대화", "상담·진료·돌봄 통화", "녹음·STT·검수·동의비용"),
        ("04", "파형·시계열", "ECG, EEG, ICU waveform, RPM", "센서·동기화·결측·연속성"),
    ]
    for col, (idx, title, examples, factors) in zip(modality_cols, modalities):
        with col:
            st.markdown(
                f"""
                <div class="modality-card">
                  <span>{idx}</span><h3>{safe_html(title)}</h3>
                  <p>{safe_html(examples)}</p><small>{safe_html(factors)}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )

    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("### 예정 평가축")
            st.markdown(
                """
                - **데이터 획득비용**: 장비 사용, 촬영·녹음·센서 시간, 전문가 수행비
                - **주석·정답지 비용**: 전문의 판독, 다중 주석, 합의·검수, 품질보증
                - **데이터 품질**: 해상도, 신호대잡음비, 완전성, 일관성, 시간 동기화
                - **보안·개인정보 비용**: 비식별화, 접근통제, 재식별 위험 관리
                - **희소성과 대표성**: 희귀질환, 병변 분포, 기관·장비 다양성
                - **활용효과**: 연구·임상·규제·AI 학습·외부검증 가치
                """
            )
    with right:
        with st.container(border=True):
            st.markdown("### 다음 개발 게이트")
            st.markdown(
                """
                1. 모달리티별 원가 드라이버 정의
                2. 표준 메타데이터 스키마 확정
                3. 주석·품질·보안 가중치 근거 수립
                4. 대표 데이터셋 회귀검증
                5. 정형 결과와 통합 포트폴리오 보고
                """
            )

    if st.button("평가 유형 다시 선택", use_container_width=True):
        set_page(SERVICE_TYPE_PAGE)


def _build_template_bytes(quality_mode: str) -> bytes:
    template = default_metadata(int(st.session_state["case_count"]))
    columns = (
        DETAILED_EDITOR_COLUMNS
        if quality_mode == QUALITY_MODE_DETAILED
        else SIMPLE_EDITOR_COLUMNS
    )
    template = template[columns].rename(columns=METADATA_KOREAN_HEADERS)
    return template.to_csv(index=False).encode("utf-8-sig")


def _apply_fee_suggestions() -> tuple[int, list[str]]:
    df = normalize_metadata_dataframe(
        st.session_state["variables_df"],
        int(st.session_state["case_count"]),
        str(st.session_state["quality_mode"]),
    )
    applied = 0
    unresolved: list[str] = []
    for index, row in df.iterrows():
        if row["component_detail"] != "Examination & Laboratory":
            continue
        if str(row["medical_fee_item"]).strip() or float(row["manual_unit_price_krw"]) > 0:
            continue
        suggestion = repository.best_fee_suggestion(
            str(row["variable_name"]), str(row["variable_description"])
        )
        if suggestion:
            df.at[index, "medical_fee_item"] = suggestion["fee_name_ko"]
            applied += 1
        else:
            unresolved.append(str(row["variable_name"]) or f"행 {index + 1}")
    st.session_state["variables_df"] = df
    return applied, unresolved


def render_input_page() -> None:
    st.session_state["data_mode"] = STRUCTURED_MODE
    section_title(
        "정형 데이터셋 정보 및 변수 메타정보",
        "환자 원자료가 아닌 데이터셋·변수 단위 메타정보를 입력합니다.",
        "STRUCTURED DATA · INPUT",
    )
    st.markdown(
        """
        <div class="input-principle">
          <b>입력 원칙</b><span>개인 식별정보와 환자 원자료를 업로드하지 않고, 변수명·건수·참조코드 등 가치평가에 필요한 메타정보만 입력합니다.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("저장한 입력 초안 불러오기"):
        draft_upload = st.file_uploader(
            "입력 초안 JSON",
            type=["json"],
            key="input_draft_uploader",
            help="이 앱에서 내려받은 ts26040-input-draft-v1/v2 JSON을 지원합니다.",
        )
        if draft_upload is not None:
            draft_payload = draft_upload.getvalue()
            draft_signature = hashlib.sha256(draft_payload).hexdigest()
            if draft_signature != st.session_state["draft_upload_signature"]:
                try:
                    restore_input_draft(draft_payload)
                    st.session_state["draft_upload_signature"] = draft_signature
                    st.success("입력 초안을 복원했습니다.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"입력 초안 복원 실패: {exc}")

    with st.container(border=True):
        st.subheader("1. 데이터셋 기본 정보")
        left, right = st.columns(2, gap="large")
        with left:
            st.session_state["dataset_name"] = st.text_input(
                "데이터셋명", value=st.session_state["dataset_name"]
            )
            st.session_state["evaluation_year"] = st.number_input(
                "평가 기준연도",
                min_value=2000,
                max_value=2100,
                value=int(st.session_state["evaluation_year"]),
                step=1,
                help="현재 참조 데이터는 KR-2025 프로파일입니다. 연도는 보고서 메타정보로 기록됩니다.",
            )
            label_to_code = {label: code for code, label in INSTITUTE_LABELS.items()}
            selected_label = INSTITUTE_LABELS[st.session_state["institute_code"]]
            institute_label = st.selectbox(
                "데이터 생산 기관종별",
                list(label_to_code.keys()),
                index=list(label_to_code.keys()).index(selected_label),
            )
            st.session_state["institute_code"] = label_to_code[institute_label]
        with right:
            st.session_state["case_count"] = st.number_input(
                "케이스 수(행)",
                min_value=1,
                value=int(st.session_state["case_count"]),
                step=1,
            )
            quality_codes = list(QUALITY_MODE_LABELS.keys())
            selected_quality = st.selectbox(
                "Step 1 품질 입력 방식",
                quality_codes,
                index=quality_codes.index(st.session_state["quality_mode"]),
                format_func=lambda code: QUALITY_MODE_LABELS[code],
                help=(
                    "간편 입력은 정확성·일관성을 100% 가정하고 완전성만 사용가능/전체로 계산합니다. "
                    "상세 입력은 정확한 수, 규칙 준수 수, 결측 수를 직접 입력합니다."
                ),
            )
            st.session_state["quality_mode"] = selected_quality
            st.text_input(
                "변수의 수(열)",
                value=str(len(st.session_state["variables_df"])),
                disabled=True,
            )

    quality_mode = str(st.session_state["quality_mode"])
    with st.container(border=True):
        title_col, action_col = st.columns([1, 1.75])
        with title_col:
            st.subheader("2. 데이터셋 메타정보")
        with action_col:
            template_col, upload_col, suggest_col, add_col = st.columns([1.1, 1.05, 1.05, 0.75])
            with template_col:
                st.download_button(
                    "템플릿 내려받기",
                    _build_template_bytes(quality_mode),
                    file_name=f"variable_metadata_template_{quality_mode}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with upload_col:
                uploaded = st.file_uploader(
                    "CSV 업로드",
                    type=["csv"],
                    label_visibility="collapsed",
                    key="metadata_uploader",
                )
            with suggest_col:
                suggest_clicked = st.button(
                    "검사 수가 추천",
                    use_container_width=True,
                    help="의료행위가 비어 있는 검사 변수에 한해 명칭 유사도가 충분히 높은 항목만 제안·적용합니다.",
                )
            with add_col:
                add_clicked = st.button("행 추가", use_container_width=True)

        if uploaded is not None:
            payload = uploaded.getvalue()
            signature = hashlib.sha256(payload).hexdigest()
            if signature != st.session_state["uploaded_signature"]:
                try:
                    uploaded_df = _read_csv_payload(payload)
                    st.session_state["variables_df"] = normalize_metadata_dataframe(
                        uploaded_df,
                        int(st.session_state["case_count"]),
                        quality_mode,
                    )
                    st.session_state["uploaded_signature"] = signature
                    st.success(f"{len(st.session_state['variables_df']):,}개 변수를 불러왔습니다.")
                except Exception as exc:
                    st.error(f"CSV 읽기 오류: {exc}")

        if suggest_clicked:
            applied, unresolved = _apply_fee_suggestions()
            if applied:
                st.success(f"{applied}개 검사 변수에 Step 2 의료행위를 적용했습니다.")
            if unresolved:
                st.warning("자동 적용하지 못한 검사 변수: " + ", ".join(unresolved))
            st.rerun()

        editor_columns = (
            DETAILED_EDITOR_COLUMNS
            if quality_mode == QUALITY_MODE_DETAILED
            else SIMPLE_EDITOR_COLUMNS
        )
        normalized_for_editor = normalize_metadata_dataframe(
            st.session_state["variables_df"],
            int(st.session_state["case_count"]),
            quality_mode,
        )[editor_columns]

        column_config: dict[str, Any] = {
            "variable_name": st.column_config.TextColumn("변수명", required=True, width="small"),
            "variable_description": st.column_config.TextColumn("변수 설명", width="medium"),
            "component_detail": st.column_config.SelectboxColumn(
                "변수 특성",
                options=repository.component_details,
                required=True,
                width="large",
            ),
            "total_count": st.column_config.NumberColumn("전체 케이스 수", min_value=0, step=1, format="%d"),
            "non_empty_count": st.column_config.NumberColumn("비어있지 않은 데이터 수", min_value=0, step=1, format="%d"),
            "accurate_count": st.column_config.NumberColumn("정확한 데이터 수", min_value=0, step=1, format="%d"),
            "rule_compliant_count": st.column_config.NumberColumn("규칙 준수 데이터 수", min_value=0, step=1, format="%d"),
            "usable_count": st.column_config.NumberColumn("사용 가능 데이터 수", min_value=0, step=1, format="%d"),
            "not_used_count": st.column_config.NumberColumn("미사용 데이터 수", min_value=0, step=1, format="%d"),
            "missing_count": st.column_config.NumberColumn("결측 데이터 수", min_value=0, step=1, format="%d"),
            "disease_icd3": st.column_config.TextColumn(
                "연관 질병 코드",
                help="Step 6 희소성에 사용할 ICD-3 코드. 예: E11",
            ),
            "medical_fee_item": st.column_config.SelectboxColumn(
                "Step 2 의료행위",
                options=[""] + repository.fee_item_labels,
                help="검사·검사실 변수에 적용할 최신 Step 2 카탈로그의 의료행위명",
                width="large",
            ),
            "manual_unit_price_krw": st.column_config.NumberColumn(
                "직접입력 수가(KRW)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                help="Step 2 카탈로그에 없는 경우에만 사용하며 선택된 의료행위보다 우선합니다.",
            ),
        }

        edited_df = st.data_editor(
            normalized_for_editor,
            key=f"variables_editor_{quality_mode}",
            num_rows="dynamic",
            use_container_width=True,
            hide_index=False,
            column_config=column_config,
        )
        st.session_state["variables_df"] = normalize_metadata_dataframe(
            edited_df,
            int(st.session_state["case_count"]),
            quality_mode,
        )

        if add_clicked:
            base = default_metadata(int(st.session_state["case_count"])).iloc[[0]].copy()
            base.loc[:, "variable_name"] = ""
            base.loc[:, "variable_description"] = ""
            base.loc[:, "component_detail"] = "Demographics"
            base.loc[:, "medical_fee_item"] = ""
            base.loc[:, "disease_icd3"] = ""
            st.session_state["variables_df"] = pd.concat(
                [st.session_state["variables_df"], base], ignore_index=True
            )
            st.rerun()

        errors, warnings = validate_metadata(
            st.session_state["variables_df"], repository, quality_mode
        )
        if errors:
            with st.expander(f"입력 오류 {len(errors)}건", expanded=True):
                for item in errors:
                    st.error(item)
        elif warnings:
            with st.expander(f"입력 경고 {len(warnings)}건"):
                for item in warnings:
                    st.warning(item)
        else:
            st.success("입력된 변수 메타정보가 유효합니다.")

    with st.expander("Step 2 의료행위 선택 참고"):
        st.caption(
            "업로드된 Step 2 데이터는 단일 fee 열을 사용합니다. 검사 변수는 의료행위명을 선택하며, 기관 규모 효과는 Step 3에서 별도로 한 번만 적용됩니다."
        )
        keyword = st.text_input("의료행위·영문명·변수명 검색", key="input_fee_search")
        fee_rows = repository.search_fees(keyword, 30)
        st.dataframe(pd.DataFrame(fee_rows), use_container_width=True, hide_index=True)

    type_col, save_col, run_col = st.columns([0.8, 1, 1.15])
    with type_col:
        if st.button("평가 유형 다시 선택", use_container_width=True):
            set_page(SERVICE_TYPE_PAGE)
    with save_col:
        st.download_button(
            "입력 초안 저장(JSON)",
            data=build_input_draft_bytes(),
            file_name="health_data_valuation_input_draft.json",
            mime="application/json",
            use_container_width=True,
        )
    with run_col:
        if st.button(
            "가치평가 실행",
            type="primary",
            use_container_width=True,
            disabled=bool(errors),
        ):
            execute_valuation(navigate_to_results=True)


def render_reference_page() -> None:
    st.session_state["data_mode"] = STRUCTURED_MODE
    section_title(
        "정형 데이터 참조 데이터베이스",
        "Step 2~7 계산에 사용되는 의료행위 수가·기관·질병·효과성 참조자료와 파일 해시를 조회합니다.",
        "STRUCTURED DATA · REFERENCES",
    )

    tab2, tab345, tab6, tab7, tab_version = st.tabs(
        [
            "Step 2 의료행위 수가",
            "Step 3~5 기관·관리",
            "Step 6 질병 희소성",
            "Step 7 효과성",
            "참조 버전",
        ]
    )

    with tab2:
        search_col, limit_col = st.columns([4, 1])
        with search_col:
            keyword = st.text_input(
                "한글·영문 의료행위명, 행위군, 데이터 변수 검색",
                placeholder="예: HbA1c, 연속혈당, 안저, ECG, creatinine",
            )
        with limit_col:
            limit = st.number_input("최대 결과", min_value=10, max_value=500, value=100, step=10)

        fee_summary = repository.fee_catalog_summary()
        summary_cols = st.columns(5)
        summary_cols[0].metric("의료행위", f"{fee_summary['total_rows']:,}건")
        summary_cols[1].metric("행위군", f"{len(fee_summary['procedure_groups']):,}개")
        summary_cols[2].metric("최소 fee", f"₩{fee_summary['minimum_fee_krw']:,.0f}")
        summary_cols[3].metric("중앙 fee", f"₩{fee_summary['median_fee_krw']:,.0f}")
        summary_cols[4].metric("최대 fee", f"₩{fee_summary['maximum_fee_krw']:,.0f}")

        fee_rows = repository.search_fees(keyword, int(limit))
        fee_frame = pd.DataFrame(fee_rows)
        if not fee_frame.empty:
            fee_frame = fee_frame.rename(
                columns={
                    "fee_name_ko": "의료행위명(한글)",
                    "fee_name_en": "의료행위명(영문)",
                    "procedure_group": "행위군",
                    "data_variable": "데이터 변수",
                    "fee": "fee(KRW)",
                }
            )
        st.dataframe(fee_frame, use_container_width=True, hide_index=True)
        st.download_button(
            "Step 2 CSV 내려받기",
            data=repository.paths.step2.read_bytes(),
            file_name="step2_medical_unit_fee.csv",
            mime="text/csv",
        )
        st.info(
            "최신 Step 2 구조는 `fee_name_ko`, `fee_name_en`, `procedure_group`, `data_variable`, `fee`입니다. "
            "`hospital_base_before_addon_krw`는 사용하지 않으며 컬럼명은 `fee`로 통일했습니다."
        )
        st.success(
            "기관별 가격을 Step 2에 중복 저장하지 않습니다. 단일 fee에 Step 3 기관규모 가중치를 한 번 적용하여 기관효과 중복을 방지합니다."
        )

    with tab345:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### Step 3 기관 규모")
            frame = pd.DataFrame(repository.step3_table())
            frame["기관종별"] = frame["institute_code"].map(INSTITUTE_LABELS)
            frame = frame[["기관종별", "institute_size_weight_pct"]].rename(
                columns={"institute_size_weight_pct": "기관규모 가중치(%)"}
            )
            st.dataframe(frame, hide_index=True, use_container_width=True)
        with c2:
            st.markdown("#### Step 4 초진진찰료")
            frame = pd.DataFrame(repository.step4_table())
            frame["기관종별"] = frame["institute_code"].map(INSTITUTE_LABELS)
            frame = frame[["기관종별", "examination_fee_krw"]].rename(
                columns={"examination_fee_krw": "초진진찰료(KRW)"}
            )
            st.dataframe(frame, hide_index=True, use_container_width=True)
        with c3:
            st.markdown("#### Step 5 데이터 관리비")
            frame = pd.DataFrame(repository.step5_table()).rename(
                columns={"data_management_weight_pct": "관리비 가중치(%)"}
            )
            st.dataframe(frame, hide_index=True, use_container_width=True)
        st.caption(
            "Supplement Table 내부 계산식: Step 3 = Step 2 × (1 + 기관가중치), Step 4 = Step 3 + 검사변수별 초진진찰료 배분액, Step 5 = Step 4 × 1.17."
        )

    with tab6:
        disease_keyword = st.text_input(
            "ICD-3 또는 질병명 검색", placeholder="예: E11, diabetes"
        )
        disease_rows = repository.search_diseases(disease_keyword, 300)
        st.dataframe(pd.DataFrame(disease_rows), use_container_width=True, hide_index=True)
        st.caption("질병코드가 없는 변수에는 희소성 가중치 0%를 적용합니다.")

    with tab7:
        st.dataframe(
            pd.DataFrame(repository.step7_table()),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("효과성 가중치는 연구·임상/공중보건·정책·산업/AI 점수 합계와 동일합니다.")

    with tab_version:
        manifest = pd.DataFrame(repository.manifest())
        st.dataframe(manifest, use_container_width=True, hide_index=True)
        st.caption("평가 결과의 재현성을 위해 각 참조 CSV의 파일명, 행 수, 바이트 수, SHA-256을 기록합니다.")


def render_about_page() -> None:
    section_title(
        "운영·검증 정보",
        "서비스 운영 주체, 방법론 책임, 참조자료 출처, 검증 및 보증 범위를 공개합니다.",
        "GOVERNANCE · ASSURANCE",
    )

    cols = st.columns(4, gap="medium")
    governance_items = [
        ("운영 주체", service_identity.operator_name, service_identity.operator_unit),
        ("방법론 책임", service_identity.methodology_owner, service_identity.methodology_basis),
        ("서비스 상태", service_identity.assurance_status, "정식 인증 전 연구·검증 단계"),
        ("평가 프로파일", PROFILE_NAME, "참조자료와 산식 버전 추적"),
    ]
    for col, (label, title, note) in zip(cols, governance_items):
        with col:
            st.markdown(
                f"""
                <div class="governance-card">
                  <span>{safe_html(label)}</span><b>{safe_html(title)}</b><small>{safe_html(note)}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("### 보증 범위와 책임")
    st.warning(service_identity.assurance_note)
    st.markdown(
        """
        - **운영기관 책임**: 평가 로직, 참조자료 버전, 계산 재현성, 서비스 운영정책을 관리합니다.
        - **외부기관 역할**: HIRA와 KOICD는 수가·통계·코드 참조자료 출처이며, 본 서비스 또는 산출값의 보증기관이 아닙니다.
        - **표준과의 관계**: ISO/TS 26040 개발 프레임워크를 방법론 기반으로 활용하나, 본 서비스가 ISO 인증 또는 적합성 인증을 받은 것으로 해석하면 안 됩니다.
        - **결과 해석**: 산출값은 모델 기반 순화폐가치이며 실제 매매가격, 보험 청구액, 지불의사금액 또는 법정 감정가가 아닙니다.
        """
    )

    source_col, handling_col = st.columns(2, gap="large")
    with source_col:
        with st.container(border=True):
            st.markdown("### 참조자료 출처")
            for item in service_identity.reference_sources:
                st.markdown(f"- {item}")
            fee_summary = repository.fee_catalog_summary()
            st.caption(
                f"현재 Step 2 카탈로그: 대표 의료행위 {fee_summary['total_rows']:,}건 · "
                f"행위군 {len(fee_summary['procedure_groups']):,}개 · 단일 fee 열"
            )
    with handling_col:
        with st.container(border=True):
            st.markdown("### 데이터 처리 원칙")
            st.write(service_identity.data_handling_note)
            st.markdown(
                """
                - 공개 배포 전 개인정보처리방침과 이용약관을 별도 확정해야 합니다.
                - 결과 저장소는 운영환경에서 접근통제·암호화·백업 정책을 적용해야 합니다.
                - 환자 단위 원자료 업로드 기능은 현재 정형 평가 범위에 포함하지 않습니다.
                """
            )

    st.markdown("### 검증·감사추적")
    fee_summary = repository.fee_catalog_summary()
    manifest = repository.manifest()
    step6_rows = next(
        (int(item.get("rows", 0)) for item in manifest if item.get("step") == "STEP6"),
        0,
    )
    check_cols = st.columns(4)
    check_cols[0].metric("Step 2 의료행위", f"{fee_summary['total_rows']:,}건")
    check_cols[1].metric("Step 2 컬럼", "5개")
    check_cols[2].metric("Step 6 질병코드", f"{step6_rows:,}건")
    check_cols[3].metric("자동시험", "계산·참조·내보내기")
    st.dataframe(pd.DataFrame(manifest), use_container_width=True, hide_index=True)

    validation_path = PROJECT_ROOT / "docs" / "VALIDATION_REPORT.md"
    governance_path = PROJECT_ROOT / "docs" / "SERVICE_GOVERNANCE.md"
    download_cols = st.columns(2)
    with download_cols[0]:
        if validation_path.exists():
            st.download_button(
                "검증 보고서 내려받기",
                validation_path.read_bytes(),
                file_name="VALIDATION_REPORT.md",
                mime="text/markdown",
                use_container_width=True,
            )
    with download_cols[1]:
        if governance_path.exists():
            st.download_button(
                "운영·보증 정책 내려받기",
                governance_path.read_bytes(),
                file_name="SERVICE_GOVERNANCE.md",
                mime="text/markdown",
                use_container_width=True,
            )

    with st.expander("배포 전 운영기관 정보 수정 방법"):
        st.markdown(
            "`data/service_identity.json` 또는 Streamlit Secrets의 `[service]` 블록으로 운영기관명, 담당조직, 연락처, 저작권자를 재정의할 수 있습니다. 공개 배포 전 실제 법인명과 책임부서 승인을 확인하십시오."
        )
        st.code(
            '[service]\noperator_name = "실제 운영기관명"\noperator_unit = "책임부서"\ncontact_email = "contact@example.org"\ncopyright_holder = "실제 저작권자"',
            language="toml",
        )


def _quality_text(value: float | None) -> str:
    return "미산출" if value is None else f"{value:.1f}%"


def render_results_page() -> None:
    st.session_state["data_mode"] = STRUCTURED_MODE
    result_df = st.session_state["result_df"]
    summary = st.session_state["result_summary"]
    dataset_info = st.session_state["result_dataset_info"]
    warnings = st.session_state["result_warnings"]

    section_title(
        "정형 헬스 데이터 가치 평가 결과",
        PROFILE_NAME,
        "STRUCTURED DATA · RESULT",
    )
    if result_df is None or summary is None or dataset_info is None:
        st.info("아직 실행된 가치평가가 없습니다.")
        if st.button("입력 화면으로 이동", type="primary"):
            set_page(INPUT_PAGE)
        return

    metric_cols = st.columns(5, gap="medium")
    with metric_cols[0]:
        metric_card(
            "헬스 데이터셋 가치",
            f"₩ {summary['total_value_krw']:,.0f}",
            "전체 변수 기준",
            "forest",
        )
    with metric_cols[1]:
        metric_card("평가 변수 수", f"{summary['variable_count']} 종", "", "rust")
    with metric_cols[2]:
        metric_card("평가 대상 데이터", f"{summary['total_usable_count']:,} 건", "", "slate")
    with metric_cols[3]:
        metric_card(
            "평균 완전성",
            _quality_text(summary["average_completeness_pct"]),
            "사용가능/전체",
            "sand",
        )
    with metric_cols[4]:
        metric_card(
            "계산 프로파일",
            "KR-2025",
            f"품질 입력 · {QUALITY_MODE_LABELS[dataset_info.quality_mode]}",
            "forest",
        )

    st.caption(
        "Step 1 품질지표는 현재 금액 승수로 사용하지 않습니다. 최종 금액은 Step 2~7 단위가치에 사용 가능 데이터 수를 곱해 산정합니다."
    )

    bar_col, donut_col, top_col = st.columns([1.25, 1.05, 0.82], gap="medium")
    component_df = summary["component_summary"]
    with bar_col:
        with st.container(border=True):
            st.markdown("#### 구성요소별 가치 분포")
            fig = px.bar(
                component_df,
                x="component_detail",
                y="final_variable_value_krw",
                text_auto=",.0f",
                labels={
                    "component_detail": "",
                    "final_variable_value_krw": "최종 가치(KRW)",
                },
            )
            fig.update_traces(marker_color="#234B45", textposition="outside")
            fig.update_layout(
                height=320,
                margin=dict(l=20, r=20, t=10, b=80),
                showlegend=False,
                xaxis_tickangle=-15,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with donut_col:
        with st.container(border=True):
            st.markdown("#### 평가 구성")
            fig = px.pie(
                component_df,
                names="component_detail",
                values="final_variable_value_krw",
                hole=0.55,
                color_discrete_sequence=[
                    "#234B45",
                    "#A86645",
                    "#667B76",
                    "#D1A865",
                    "#526A7A",
                    "#8E7865",
                ],
            )
            fig.update_layout(height=270, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.success(
                f"평가 완료 · {st.session_state['last_run_at']} · "
                f"효과성 평균 {summary['average_effectiveness_pct']:.1f}%"
            )
    with top_col:
        with st.container(border=True):
            st.markdown("#### 상위 가치 변수 TOP 5")
            for rank, (_, row) in enumerate(summary["top5"].iterrows(), start=1):
                st.markdown(
                    f"**{rank}. {row['variable_name']}**  \n"
                    f"{row['final_variable_value_krw']:,.0f}원"
                )

    with st.container(border=True):
        table_title, download_actions = st.columns([1, 1.45])
        with table_title:
            st.markdown("### 변수별 가치 평가 결과")
        csv_bytes = build_csv_bytes(result_df)
        excel_bytes = build_excel_bytes(
            dataset_info,
            result_df,
            summary,
            repository.manifest(),
            warnings,
            identity=service_identity,
        )
        html_bytes = build_html_report(
            dataset_info, result_df, summary, warnings, identity=service_identity
        )
        json_bytes = build_json_bytes(
            dataset_info, result_df, summary, warnings, identity=service_identity
        )
        with download_actions:
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.download_button(
                    "CSV",
                    csv_bytes,
                    file_name="health_data_valuation_result.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with d2:
                st.download_button(
                    "Excel",
                    excel_bytes,
                    file_name="health_data_valuation_result.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with d3:
                st.download_button(
                    "결과보고서",
                    html_bytes,
                    file_name="health_data_valuation_report.html",
                    mime="text/html",
                    use_container_width=True,
                )
            with d4:
                st.download_button(
                    "감사추적 JSON",
                    json_bytes,
                    file_name="health_data_valuation_audit.json",
                    mime="application/json",
                    use_container_width=True,
                )

        display_columns = [
            "variable_name",
            "variable_description",
            "component_detail",
            "usable_count",
            "step1_completeness_pct",
            "fee_name_ko",
            "step2_fee_krw",
            "scarcity_weight_pct",
            "effectiveness_weight_pct",
            "final_variable_value_krw",
        ]
        display = result_df[display_columns].copy()
        display.columns = [
            "변수명",
            "변수 설명",
            "변수 특성",
            "사용 가능 데이터 수",
            "완전성(%)",
            "Step 2 의료행위",
            "Step 2 fee(KRW)",
            "희소성 가중치(%)",
            "효과성 가중치(%)",
            "변수별 가치(KRW)",
        ]
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Step 2 fee(KRW)": st.column_config.NumberColumn(format="%.2f"),
                "변수별 가치(KRW)": st.column_config.NumberColumn(format="%.2f"),
                "완전성(%)": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        with st.expander("Step 1~7 전체 계산추적"):
            st.dataframe(result_df, use_container_width=True, hide_index=True)

    if warnings:
        with st.expander(f"평가 경고 {len(warnings)}건", expanded=True):
            for item in warnings:
                st.warning(item)

    if not durable_store:
        st.info(
            "현재 저장소는 로컬 SQLite입니다. Streamlit Community Cloud에서 앱 재시작·재배포 시 영구 보존되지 않을 수 있습니다. 운영 배포는 secrets의 database.url에 원격 PostgreSQL을 설정하십시오."
        )

    back_col, recalc_col, save_col = st.columns(3)
    with back_col:
        if st.button("입력 화면으로 돌아가기", use_container_width=True):
            set_page(INPUT_PAGE)
    with recalc_col:
        if st.button("다시 평가하기", use_container_width=True):
            if execute_valuation(navigate_to_results=False):
                st.success("현재 입력값으로 다시 계산했습니다.")
                st.rerun()
    with save_col:
        if st.button("최종 결과 저장", type="primary", use_container_width=True):
            try:
                run_id = store.save(dataset_info, result_df, summary, warnings)
                st.session_state["saved_run_id"] = run_id
                st.success(f"최종 결과 저장 완료: {run_id}")
            except Exception as exc:
                st.error(f"최종 결과 저장 실패: {exc}")

    with st.expander("최근 저장 결과"):
        try:
            recent_runs = pd.DataFrame(store.list_recent(limit=20))
            if recent_runs.empty:
                st.info("저장된 결과가 없습니다.")
            else:
                st.dataframe(recent_runs, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.warning(f"최근 저장 결과를 불러오지 못했습니다: {exc}")


page = st.session_state["page"]
if page == HOME_PAGE:
    render_home()
elif page == SERVICE_TYPE_PAGE:
    render_service_type_page()
elif page == INPUT_PAGE:
    render_input_page()
elif page == REFERENCE_PAGE:
    render_reference_page()
elif page == RESULT_PAGE:
    render_results_page()
elif page == UNSTRUCTURED_PAGE:
    render_unstructured_page()
elif page == ABOUT_PAGE:
    render_about_page()
else:
    set_page(HOME_PAGE)

render_footer(service_identity)
