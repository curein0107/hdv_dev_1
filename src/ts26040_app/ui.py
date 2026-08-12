from __future__ import annotations

import base64
import html
from datetime import date
from pathlib import Path

import streamlit as st

from .config import (
    APP_TITLE,
    APP_VERSION,
    ASSETS_DIR,
    PROFILE_NAME,
    STRUCTURED_SERVICE_TITLE,
    UNSTRUCTURED_SERVICE_TITLE,
)
from .identity import ServiceIdentity
from .state import (
    ABOUT_PAGE,
    HOME_PAGE,
    INPUT_PAGE,
    REFERENCE_PAGE,
    RESULT_PAGE,
    SERVICE_TYPE_PAGE,
    STRUCTURED_MODE,
    UNSTRUCTURED_MODE,
    UNSTRUCTURED_PAGE,
    navigate,
    pages_for_mode,
)


def load_css() -> None:
    css_path = ASSETS_DIR / "styles.css"
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _svg_data_uri(path: Path) -> str:
    content = path.read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(content).decode("ascii")


def _safe(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def render_top_header(identity: ServiceIdentity) -> None:
    logo_uri = _svg_data_uri(ASSETS_DIR / "logo.svg")
    operator = _safe(identity.operator_name)
    status = _safe(identity.assurance_status)
    st.markdown(
        f"""
        <div class="app-topbar">
          <div class="brand-group">
            <img src="{logo_uri}" class="brand-logo" alt="health data valuation service mark" />
            <div class="brand-lockup">
              <div class="brand-title">{_safe(APP_TITLE)}</div>
              <div class="brand-subtitle">Health Data Valuation Service</div>
            </div>
            <div class="version-pill">{_safe(APP_VERSION)}</div>
          </div>
          <div class="topbar-meta">
            <span class="topbar-status">{status}</span>
            <span class="topbar-operator">운영 · {operator}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(identity: ServiceIdentity) -> None:
    mode = st.session_state.get("data_mode")
    with st.sidebar:
        st.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)

        if mode == STRUCTURED_MODE:
            mode_title = STRUCTURED_SERVICE_TITLE
            mode_note = PROFILE_NAME
        elif mode == UNSTRUCTURED_MODE:
            mode_title = UNSTRUCTURED_SERVICE_TITLE
            mode_note = "확장 설계 · 준비 중"
        else:
            mode_title = "평가 유형을 선택하세요"
            mode_note = "정형 · 비정형 확장 구조"

        st.markdown(
            f"""
            <div class="sidebar-mode-card">
              <span>현재 서비스 영역</span>
              <b>{_safe(mode_title)}</b>
              <small>{_safe(mode_note)}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        icons = {
            HOME_PAGE: "⌂",
            SERVICE_TYPE_PAGE: "◇",
            INPUT_PAGE: "▦",
            REFERENCE_PAGE: "≡",
            RESULT_PAGE: "∑",
            UNSTRUCTURED_PAGE: "∿",
            ABOUT_PAGE: "ⓘ",
        }
        current = st.session_state["page"]
        for page in pages_for_mode(mode):
            button_type = "primary" if page == current else "secondary"
            if st.button(
                f"{icons[page]}  {page}",
                key=f"nav_{page}",
                type=button_type,
                use_container_width=True,
            ):
                navigate(page)

        st.markdown("---")
        st.markdown(
            f"""
            <div class="sidebar-governance-card">
              <span>운영·검증 상태</span>
              <b>{_safe(identity.operator_name)}</b>
              <small>{_safe(identity.assurance_status)}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("가치평가 방법 안내", use_container_width=True):
            st.session_state["show_guide"] = True
            navigate(HOME_PAGE)
        st.caption("사이드바 접기·펼치기는 브라우저 좌측 상단 아이콘을 사용합니다.")


def metric_card(title: str, value: str, subtitle: str = "", accent: str = "forest") -> None:
    st.markdown(
        f"""
        <div class="metric-card metric-{_safe(accent)}">
          <div class="metric-title">{title}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def feature_card(index: str, title: str, text: str, accent: str = "forest") -> None:
    st.markdown(
        f"""
        <div class="feature-card feature-{_safe(accent)}">
          <div class="feature-index">{_safe(index)}</div>
          <div><h3>{_safe(title)}</h3><p>{_safe(text)}</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    eyebrow_html = f'<span class="page-eyebrow">{_safe(eyebrow)}</span>' if eyebrow else ""
    st.markdown(
        f"""
        <div class="page-heading">
          {eyebrow_html}
          <h2>{_safe(title)}</h2>
          <p>{_safe(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home_preview() -> None:
    st.markdown(
        """
        <div class="method-board">
          <div class="method-board-head">
            <span>VALUATION LOGIC</span>
            <b>가치가 만들어지는 경로</b>
          </div>
          <div class="method-flow">
            <div><small>01</small><b>생성비용</b><span>의료행위·조사·측정</span></div>
            <i>+</i>
            <div><small>02</small><b>생산·관리</b><span>기관·품질·보안</span></div>
            <i>+</i>
            <div><small>03</small><b>희소성</b><span>질병·코호트 가용성</span></div>
            <i>+</i>
            <div><small>04</small><b>활용효과</b><span>연구·임상·정책·산업</span></div>
          </div>
          <div class="method-result">
            <span>MODEL OUTPUT</span>
            <strong>모델 기반 순화폐가치</strong>
            <p>입력 메타정보와 참조자료 버전을 함께 기록해 산정 근거를 추적합니다.</p>
          </div>
          <div class="method-disclaimer">시장 거래가격·법정 감정가·보험 청구액과는 구분됩니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_identity_strip(identity: ServiceIdentity) -> None:
    st.markdown(
        f"""
        <div class="identity-strip">
          <div><span>운영 주체</span><b>{_safe(identity.operator_name)}</b><small>{_safe(identity.operator_unit)}</small></div>
          <div><span>방법론 기반</span><b>{_safe(identity.methodology_basis)}</b><small>{_safe(identity.methodology_owner)}</small></div>
          <div><span>검증 상태</span><b>{_safe(identity.assurance_status)}</b><small>공식 인증 여부는 운영·검증 정보에서 확인</small></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def guide_content() -> None:
    st.markdown(
        """
        ### 정형 헬스 데이터 가치평가 계산 절차

        1. **Step 1 — 데이터 품질 확인**: 정확성은 `정확한 데이터 수 / 비어있지 않은 데이터 수`, 완전성은 `사용 가능 데이터 수 / 전체 데이터 수`, 일관성은 `규칙 준수 데이터 수 / 비어있지 않은 데이터 수`로 계산합니다. 현재 참조자료에는 통과 임계값이 없어 품질지표는 표시·감사추적에 사용하고 화폐가치에 곱하지 않습니다.
        2. **Step 2 — 데이터 생성 단가**: 검사·영상·생체신호 변수는 `step2_medical_unit_fee.csv`의 단일 `fee` 값을 적용합니다. 인구학·설문·식이 변수는 Supplement Table의 5,610원을 해당 대분류 변수 수로 균등 배분합니다.
        3. **Step 3 — 데이터 생산기관 규모**: 의원·병원·종합병원·상급종합병원 가중치 15%·20%·25%·30%를 Step 2 값에 한 번 적용합니다.
        4. **Step 4 — 검사 수행 기반비용**: 기관종별 초진진찰료를 전체 검사·검사실 변수 수로 균등 배분하여 해당 변수에 가산합니다.
        5. **Step 5 — 데이터 관리비**: 원본 데이터 저장·보안·품질관리 비용 가중치 17%를 적용합니다.
        6. **Step 6 — 질병 희소성**: 2025년 3단상병 통계의 질병별 유병률 구간에 따른 음의 가중치를 적용합니다. 질병코드가 없으면 0%입니다.
        7. **Step 7 — 활용 효과성**: 구성요소별 연구, 임상·공중보건, 정책, 산업·AI 점수 합산 가중치를 적용합니다.
        8. **최종 변수 가치**: `Step 7 단위가치 × 사용 가능 데이터 수`로 산정하고, 모든 중간값은 반올림하지 않은 채 감사추적표에 기록합니다.

        **Step 2 변경사항**  
        최신 파일은 `fee_name_ko`, `fee_name_en`, `procedure_group`, `data_variable`, `fee`의 5개 열과 대표 의료행위 103건으로 구성됩니다. 기존의 `hospital_base_before_addon_krw` 및 기관별 가격 열은 사용하지 않습니다. 기관효과는 Step 3에서만 적용하므로 중복 가중을 방지합니다.

        **해석상 주의**  
        산출값은 Supplement Table의 내부 계산 논리를 구현한 모델 기반 순화폐가치입니다. 실제 시장가격, 보험 청구액, 지불의사금액 또는 법정 감정가와 동일하지 않습니다.
        """
    )


def render_footer(identity: ServiceIdentity) -> None:
    contact = (
        f'<span>문의 · <a href="mailto:{_safe(identity.contact_email)}">{_safe(identity.contact_email)}</a></span>'
        if identity.contact_email
        else ""
    )
    st.markdown(
        f"""
        <div class="service-footer">
          <div>
            <b>{_safe(APP_TITLE)}</b>
            <span>© {date.today().year} {_safe(identity.copyright_holder)}. All rights reserved.</span>
          </div>
          <div class="footer-meta">
            <span>{_safe(identity.assurance_status)}</span>
            <span>참조자료의 권리는 각 원 출처에 귀속</span>
            {contact}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
