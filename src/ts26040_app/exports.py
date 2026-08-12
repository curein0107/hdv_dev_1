from __future__ import annotations

import html
import io
import json
from datetime import datetime
from typing import Any

import pandas as pd

from .config import APP_TITLE, APP_VERSION, METHODOLOGY_NAME, PROFILE_NAME
from .identity import ServiceIdentity
from .models import DatasetInfo


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    try:
        return value.item()
    except AttributeError:
        return str(value)


def build_csv_bytes(result_df: pd.DataFrame) -> bytes:
    return result_df.to_csv(index=False).encode("utf-8-sig")


def build_json_bytes(
    dataset_info: DatasetInfo,
    result_df: pd.DataFrame,
    summary: dict[str, Any],
    warnings: list[str],
    identity: ServiceIdentity | None = None,
) -> bytes:
    payload = {
        "dataset": {
            "dataset_name": dataset_info.dataset_name,
            "evaluation_year": dataset_info.evaluation_year,
            "institute_code": dataset_info.institute_code,
            "case_count": dataset_info.case_count,
            "quality_mode": dataset_info.quality_mode,
        },
        "service": {
            "title": APP_TITLE,
            "version": APP_VERSION,
            "operator_name": identity.operator_name if identity else "",
            "operator_unit": identity.operator_unit if identity else "",
            "methodology_basis": (
                identity.methodology_basis if identity else METHODOLOGY_NAME
            ),
            "assurance_status": identity.assurance_status if identity else "",
            "assurance_note": identity.assurance_note if identity else "",
        },
        "profile": PROFILE_NAME,
        "summary": {
            key: value
            for key, value in summary.items()
            if key not in {"component_summary", "top5"}
        },
        "warnings": warnings,
        "results": result_df.to_dict(orient="records"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        default=_json_default,
    ).encode("utf-8")


def build_excel_bytes(
    dataset_info: DatasetInfo,
    result_df: pd.DataFrame,
    summary: dict[str, Any],
    reference_manifest: list[dict[str, Any]],
    warnings: list[str],
    identity: ServiceIdentity | None = None,
) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_format = workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#203D38",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )
        money_format = workbook.add_format({"num_format": "#,##0.00"})
        percent_format = workbook.add_format({"num_format": "0.00"})

        summary_df = pd.DataFrame(
            {
                "item": [
                    "Dataset",
                    "Evaluation year",
                    "Institution code",
                    "Case count",
                    "Quality mode",
                    "Service",
                    "Service version",
                    "Operator",
                    "Assurance status",
                    "Methodology basis",
                    "Profile",
                    "Variable count",
                    "Total usable data",
                    "Total value (KRW)",
                    "Generated at",
                ],
                "value": [
                    dataset_info.dataset_name,
                    dataset_info.evaluation_year,
                    dataset_info.institute_code,
                    dataset_info.case_count,
                    dataset_info.quality_mode,
                    APP_TITLE,
                    APP_VERSION,
                    identity.operator_name if identity else "",
                    identity.assurance_status if identity else "",
                    identity.methodology_basis if identity else METHODOLOGY_NAME,
                    PROFILE_NAME,
                    summary["variable_count"],
                    summary["total_usable_count"],
                    summary["total_value_krw"],
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ],
            }
        )
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        result_df.to_excel(writer, sheet_name="Variable Results", index=False)

        trace_columns = [
            "variable_name",
            "step2_unit_price_krw",
            "step3_value_krw",
            "step4_value_krw",
            "step5_value_krw",
            "scarcity_weight_pct",
            "step6_value_krw",
            "effectiveness_weight_pct",
            "step7_unit_value_krw",
            "usable_count",
            "final_variable_value_krw",
            "warning",
        ]
        result_df[trace_columns].to_excel(
            writer, sheet_name="Step Trace", index=False
        )
        pd.DataFrame(reference_manifest).to_excel(
            writer, sheet_name="Reference Manifest", index=False
        )
        pd.DataFrame({"warning": warnings or [""]}).to_excel(
            writer, sheet_name="Warnings", index=False
        )

        for sheet_name, frame in {
            "Summary": summary_df,
            "Variable Results": result_df,
            "Step Trace": result_df[trace_columns],
            "Reference Manifest": pd.DataFrame(reference_manifest),
            "Warnings": pd.DataFrame({"warning": warnings or [""]}),
        }.items():
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes(1, 0)
            for column_index, column_name in enumerate(frame.columns):
                worksheet.write(0, column_index, column_name, header_format)
                max_length = max(
                    len(str(column_name)),
                    *(
                        len(str(value))
                        for value in frame[column_name].head(200).fillna("")
                    ),
                )
                worksheet.set_column(
                    column_index,
                    column_index,
                    min(max_length + 2, 42),
                )

            for column_index, column_name in enumerate(frame.columns):
                if column_name.endswith("_krw") or "value (KRW)" in column_name:
                    worksheet.set_column(column_index, column_index, 18, money_format)
                if column_name.endswith("_pct"):
                    worksheet.set_column(column_index, column_index, 14, percent_format)

    output.seek(0)
    return output.getvalue()


def _table_html(dataframe: pd.DataFrame) -> str:
    return dataframe.to_html(
        index=False,
        border=0,
        classes="result-table",
        escape=True,
        float_format=lambda value: f"{value:,.2f}",
    )


def build_html_report(
    dataset_info: DatasetInfo,
    result_df: pd.DataFrame,
    summary: dict[str, Any],
    warnings: list[str],
    identity: ServiceIdentity | None = None,
) -> bytes:
    component = summary["component_summary"].copy()
    component["final_variable_value_krw"] = component[
        "final_variable_value_krw"
    ].map(lambda value: f"{value:,.2f}")

    display_columns = [
        "variable_name",
        "variable_description",
        "component_detail",
        "total_count",
        "usable_count",
        "step2_unit_price_krw",
        "step3_value_krw",
        "step4_value_krw",
        "step5_value_krw",
        "scarcity_weight_pct",
        "step6_value_krw",
        "effectiveness_weight_pct",
        "step7_unit_value_krw",
        "final_variable_value_krw",
        "warning",
    ]
    warning_html = (
        "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in warnings) + "</ul>"
        if warnings
        else "<p>평가 경고 없음</p>"
    )
    operator_name = html.escape(identity.operator_name) if identity else "운영기관 미기재"
    operator_unit = html.escape(identity.operator_unit) if identity else ""
    assurance_status = (
        html.escape(identity.assurance_status) if identity else "모델 기반 평가"
    )
    assurance_note = (
        html.escape(identity.assurance_note)
        if identity
        else "외부 표준·참조자료 제공기관이 본 산출값을 공식 인증·보증하는 것은 아닙니다."
    )
    methodology_basis = (
        html.escape(identity.methodology_basis) if identity else html.escape(METHODOLOGY_NAME)
    )
    copyright_holder = (
        html.escape(identity.copyright_holder) if identity else html.escape(APP_TITLE)
    )

    document = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{html.escape(APP_TITLE)} 결과보고서</title>
<style>
body {{ font-family: Arial, 'Malgun Gothic', sans-serif; margin: 36px; color: #1e2927; background: #f3f0e8; }}
.report {{ max-width: 1280px; margin: 0 auto; padding: 34px; border: 1px solid #d7d1c4; background: #fffdf7; }}
h1 {{ margin: 0; color: #162f2b; border-bottom: 3px solid #a76543; padding-bottom: 14px; }}
h2 {{ margin-top: 34px; color: #203d38; border-bottom: 1px solid #d7d1c4; padding-bottom: 8px; }}
.meta {{ color: #69736f; font-size: 13px; line-height: 1.7; }}
.governance {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0; margin: 22px 0; border: 1px solid #d7d1c4; }}
.governance div {{ padding: 14px; border-right: 1px solid #d7d1c4; }}
.governance div:last-child {{ border-right: 0; }}
.governance span {{ display: block; color: #a76543; font-size: 10px; font-weight: bold; }}
.governance b {{ display: block; margin-top: 6px; color: #203d38; }}
.summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
.card {{ border: 1px solid #d7d1c4; border-left: 4px solid #203d38; padding: 16px; background: #fffdf7; }}
.card strong {{ display: block; color: #203d38; font-size: 23px; margin-top: 10px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th {{ background: #203d38; color: white; padding: 8px; }}
td {{ border: 1px solid #d7d1c4; padding: 7px; }}
.notice {{ background: #f4eddf; border: 1px solid #c9a66b; padding: 14px; }}
.assurance {{ margin-top: 18px; padding: 14px; border-left: 4px solid #a76543; background: #f2e7df; color: #5d4335; font-size: 12px; line-height: 1.7; }}
.footer {{ margin-top: 40px; padding-top: 14px; border-top: 1px solid #d7d1c4; font-size: 11px; color: #69736f; }}
</style>
</head>
<body>
<div class="report">
<h1>{html.escape(APP_TITLE)} 결과보고서</h1>
<p class="meta"><b>프로파일:</b> {html.escape(PROFILE_NAME)}<br><b>데이터셋:</b> {html.escape(dataset_info.dataset_name)} · <b>평가기준연도:</b> {dataset_info.evaluation_year} · <b>기관코드:</b> {html.escape(dataset_info.institute_code)} · <b>품질 입력:</b> {html.escape(dataset_info.quality_mode)}</p>
<div class="governance">
<div><span>운영 주체</span><b>{operator_name}</b><small>{operator_unit}</small></div>
<div><span>방법론 기반</span><b>{methodology_basis}</b></div>
<div><span>검증 상태</span><b>{assurance_status}</b></div>
</div>
<div class="assurance">{assurance_note}</div>
<div class="summary">
<div class="card">총 데이터 가치<strong>₩ {summary['total_value_krw']:,.2f}</strong></div>
<div class="card">평가 변수 수<strong>{summary['variable_count']}</strong></div>
<div class="card">총 사용가능 데이터<strong>{summary['total_usable_count']:,}</strong></div>
<div class="card">효과성 가중치 평균<strong>{summary['average_effectiveness_pct']:.2f}%</strong></div>
</div>
<h2>계산 절차</h2>
<ol>
<li>Step 1: 정확성·완전성·일관성 품질지표 계산(현재 금액 승수로 미사용)</li>
<li>Step 2: 설문 기준비용 분배 또는 최신 Step 2 단일 fee 의료행위 단가 적용</li>
<li>Step 3: 기관 규모 가중치를 Step 2 값에 한 번 적용</li>
<li>Step 4: 기관종별 초진진찰료를 검사 변수에 배분</li>
<li>Step 5: 원본 데이터 저장·관리 비용 가중치 적용</li>
<li>Step 6: 2025 HIRA 3단상병 통계 기반 희소성 가중치 적용</li>
<li>Step 7: 구성요소별 효과성 가중치 적용</li>
<li>최종 변수 가치: Step 7 단위가치 × 사용 가능 데이터 수</li>
</ol>
<h2>구성요소별 가치</h2>
{_table_html(component)}
<h2>변수별 가치평가 결과</h2>
{_table_html(result_df[display_columns])}
<h2>평가 경고</h2>
<div class="notice">{warning_html}</div>
<div class="footer">생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 본 산출값은 모델 기반 순화폐가치이며 시장 거래가격 또는 법정 감정가가 아닙니다.<br>© {datetime.now().year} {copyright_holder}. All rights reserved.</div>
</div>
</body>
</html>"""
    return document.encode("utf-8")
