from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation, getcontext
from typing import Any

import pandas as pd

from .config import (
    DETAILED_EDITOR_COLUMNS,
    DIETARY_DETAILS,
    METADATA_COLUMNS,
    NON_VALUED_COMPONENT,
    QUALITY_MODE_DETAILED,
    QUALITY_MODE_SIMPLE,
    QUESTIONNAIRE_DETAILS,
    SURVEY_REFERENCE_FEE_KRW,
)
from .models import CalculationOutput, DatasetInfo
from .references import ReferenceRepository

# Keep enough precision to reproduce the supplementary-table formula chain.
# Rounding is intentionally deferred to UI/export formatting.
getcontext().prec = 28


COUNT_COLUMNS = [
    "total_count",
    "non_empty_count",
    "accurate_count",
    "rule_compliant_count",
    "usable_count",
    "not_used_count",
    "missing_count",
]
TEXT_COLUMNS = [
    "variable_name",
    "variable_description",
    "component_detail",
    "disease_icd3",
    "medical_fee_item",
]


def to_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text.casefold() in {"nan", "none", "null"}:
        return Decimal(default)
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal(default)


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(round(float(str(value).replace(",", ""))))
    except (TypeError, ValueError):
        return default


def safe_pct(numerator: int, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return Decimal(numerator) * Decimal("100") / Decimal(denominator)


def component_group_from_detail(detail: str) -> str:
    """Map the Step 7 detail to the four valued survey groups plus exclusions."""
    if detail == "Demographics":
        return "Demographics data"
    if detail in QUESTIONNAIRE_DETAILS:
        return "Questionnaire data"
    if detail == "Examination & Laboratory":
        return "Examination & Laboratory data"
    if detail in DIETARY_DETAILS:
        return "Dietary data"
    return "Weight & Not Used & Etc data"


def _clean_component(value: Any) -> str:
    text = str(value or "").strip()
    aliases = {
        "Demographics data": "Demographics",
        "Questionnaire data": "Disease & Health States",
        "Examination & Laboratory data": "Examination & Laboratory",
        "Examination & Laborator data": "Examination & Laboratory",
        "Dietary data": "Dietary behavior",
        "Weight & Not Used & Etc data": NON_VALUED_COMPONENT,
        "Weight & Not Used & Etc": NON_VALUED_COMPONENT,
    }
    return aliases.get(text, text)


def normalize_metadata_dataframe(
    dataframe: pd.DataFrame,
    default_count: int | None = None,
    quality_mode: str = QUALITY_MODE_SIMPLE,
) -> pd.DataFrame:
    """Normalize Korean/English uploads into the canonical metadata schema.

    The context mock-up only requires total and usable counts. In simple mode,
    the additional Step 1 count fields are derived for storage while accuracy
    and consistency are marked as assumptions in the calculation output. In
    detailed mode, the user-supplied counts are preserved and validated.
    """

    aliases = {
        # Identification
        "변수명": "variable_name",
        "변수 설명": "variable_description",
        "변수설명": "variable_description",
        "변수 특성": "component_detail",
        "변수특성": "component_detail",
        "component": "component_detail",
        "component survey group detail": "component_detail",
        # Step 1 counts
        "전체 케이스 수": "total_count",
        "전체케이스수": "total_count",
        "total cases": "total_count",
        "비어있지 않은 데이터 수": "non_empty_count",
        "비어있지않은데이터수": "non_empty_count",
        "non-empty data count": "non_empty_count",
        "정확한 데이터 수": "accurate_count",
        "정확한데이터수": "accurate_count",
        "accurate data count": "accurate_count",
        "규칙 준수 데이터 수": "rule_compliant_count",
        "규칙준수데이터수": "rule_compliant_count",
        "rule-compliant data count": "rule_compliant_count",
        "사용 가능 데이터 수": "usable_count",
        "사용가능데이터수": "usable_count",
        "available data count": "usable_count",
        "미사용 데이터 수": "not_used_count",
        "미사용데이터수": "not_used_count",
        "not used data count": "not_used_count",
        "결측 데이터 수": "missing_count",
        "결측데이터수": "missing_count",
        "missing data count": "missing_count",
        # Step 2/6 mapping
        "연관 질병 코드": "disease_icd3",
        "연관질병코드": "disease_icd3",
        "icd3": "disease_icd3",
        "수가코드": "medical_fee_item",  # backward-compatible upload alias
        "의료수가코드": "medical_fee_item",
        "의료행위": "medical_fee_item",
        "step 2 의료행위": "medical_fee_item",
        "medical_fee_code": "medical_fee_item",
        "직접입력 수가": "manual_unit_price_krw",
        "직접입력수가": "manual_unit_price_krw",
        "manual fee": "manual_unit_price_krw",
    }

    df = dataframe.copy() if dataframe is not None else pd.DataFrame()
    renamed: list[str] = []
    for column in df.columns:
        raw = str(column).strip()
        renamed.append(aliases.get(raw, aliases.get(raw.casefold(), raw)))
    df.columns = renamed

    for column in METADATA_COLUMNS:
        if column not in df.columns:
            if column in COUNT_COLUMNS or column == "manual_unit_price_krw":
                df[column] = 0
            else:
                df[column] = ""

    df = df[METADATA_COLUMNS].copy()

    for column in TEXT_COLUMNS:
        df[column] = df[column].fillna("").astype(str).str.strip()

    df["component_detail"] = df["component_detail"].map(_clean_component)
    df["disease_icd3"] = (
        df["disease_icd3"].str.upper().str.replace(r"[^A-Z0-9]", "", regex=True).str[:3]
    )

    for column in COUNT_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).round().astype(int)
    df["manual_unit_price_krw"] = (
        pd.to_numeric(df["manual_unit_price_krw"], errors="coerce").fillna(0.0).astype(float)
    )

    if default_count is not None:
        default_count = max(0, int(default_count))
        df.loc[df["total_count"] <= 0, "total_count"] = default_count

    if quality_mode == QUALITY_MODE_SIMPLE:
        # Compact input deliberately does not ask users to fabricate accuracy or
        # consistency audits. The counts are stored as explicit assumptions and
        # the output identifies them as such.
        df["non_empty_count"] = df["total_count"]
        df["accurate_count"] = df["non_empty_count"]
        df["rule_compliant_count"] = df["non_empty_count"]
        df["not_used_count"] = (df["total_count"] - df["usable_count"]).clip(lower=0)
        df["missing_count"] = 0
    elif quality_mode == QUALITY_MODE_DETAILED:
        # When an uploaded detailed template omits derived support counts, fill
        # only unambiguously derivable values. Explicit non-zero entries remain.
        missing_non_empty = df["non_empty_count"] <= 0
        derivable_non_empty = (df["total_count"] - df["missing_count"]).clip(lower=0)
        df.loc[missing_non_empty, "non_empty_count"] = derivable_non_empty[missing_non_empty]

        missing_not_used = df["not_used_count"] <= 0
        derivable_not_used = (df["total_count"] - df["usable_count"]).clip(lower=0)
        df.loc[missing_not_used, "not_used_count"] = derivable_not_used[missing_not_used]
    else:
        raise ValueError(f"지원하지 않는 품질 입력 모드입니다: {quality_mode}")

    keep = (
        df["variable_name"].ne("")
        | df["variable_description"].ne("")
        | df["component_detail"].ne("")
        | df["total_count"].gt(0)
        | df["usable_count"].gt(0)
    )
    return df.loc[keep].reset_index(drop=True)


def validate_metadata(
    dataframe: pd.DataFrame,
    repository: ReferenceRepository,
    quality_mode: str = QUALITY_MODE_SIMPLE,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    valid_components = set(repository.component_details)

    if dataframe is None or dataframe.empty:
        return ["평가할 변수가 없습니다."], []

    for index, row in dataframe.iterrows():
        row_number = index + 1
        label = str(row.get("variable_name", "")).strip() or f"행 {row_number}"
        detail = str(row.get("component_detail", "")).strip()

        if not str(row.get("variable_name", "")).strip():
            errors.append(f"{label}: 변수명이 없습니다.")
        if detail not in valid_components:
            errors.append(f"{label}: 지원하지 않는 변수 특성입니다 ({detail or '미입력'}).")

        counts = {column: to_int(row.get(column)) for column in COUNT_COLUMNS}
        for column, value in counts.items():
            if value < 0:
                errors.append(f"{label}: {column}에는 음수를 입력할 수 없습니다.")
        if counts["usable_count"] > counts["total_count"]:
            errors.append(f"{label}: 사용 가능 데이터 수가 전체 케이스 수보다 큽니다.")

        if quality_mode == QUALITY_MODE_DETAILED:
            if counts["non_empty_count"] > counts["total_count"]:
                errors.append(f"{label}: 비어있지 않은 데이터 수가 전체 케이스 수보다 큽니다.")
            if counts["accurate_count"] > counts["non_empty_count"]:
                errors.append(f"{label}: 정확한 데이터 수가 비어있지 않은 데이터 수보다 큽니다.")
            if counts["rule_compliant_count"] > counts["non_empty_count"]:
                errors.append(f"{label}: 규칙 준수 데이터 수가 비어있지 않은 데이터 수보다 큽니다.")
            if counts["missing_count"] > counts["total_count"]:
                errors.append(f"{label}: 결측 데이터 수가 전체 케이스 수보다 큽니다.")
            if counts["not_used_count"] > counts["total_count"]:
                errors.append(f"{label}: 미사용 데이터 수가 전체 케이스 수보다 큽니다.")
            if counts["non_empty_count"] + counts["missing_count"] != counts["total_count"]:
                warnings.append(
                    f"{label}: 비어있지 않은 수 + 결측 수가 전체 케이스 수와 일치하지 않습니다. "
                    "품질지표는 입력값 그대로 계산됩니다."
                )
            if counts["usable_count"] + counts["not_used_count"] != counts["total_count"]:
                warnings.append(
                    f"{label}: 사용 가능 수 + 미사용 수가 전체 케이스 수와 일치하지 않습니다. "
                    "최종가치는 사용 가능 데이터 수를 기준으로 계산됩니다."
                )

        if detail == "Examination & Laboratory":
            fee = repository.lookup_fee(
                fee_item=row.get("medical_fee_item", ""),
                manual_unit_price_krw=row.get("manual_unit_price_krw", 0),
                variable_name=row.get("variable_name", ""),
                variable_description=row.get("variable_description", ""),
            )
            if fee.unit_price_krw <= 0:
                errors.append(f"{label}: {fee.warning or 'Step 2 의료행위 수가를 확인하십시오.'}")
            elif fee.source == "exact_auto_match":
                warnings.append(
                    f"{label}: Step 2 의료행위를 변수명/설명의 정확 일치로 자동 매핑했습니다 "
                    f"({fee.fee_name_ko})."
                )
        elif str(row.get("medical_fee_item", "")).strip() or to_decimal(
            row.get("manual_unit_price_krw", 0)
        ) > 0:
            warnings.append(f"{label}: 검사·검사실 외 변수의 Step 2 의료행위 입력값은 계산에 사용하지 않습니다.")

        disease_code = str(row.get("disease_icd3", "")).strip()
        if disease_code:
            scarcity = repository.get_scarcity(disease_code)
            if scarcity.warning:
                warnings.append(f"{label}: {scarcity.warning}")

    duplicate_names = sorted(
        set(dataframe.loc[dataframe["variable_name"].duplicated(), "variable_name"]) - {""}
    )
    if duplicate_names:
        warnings.append("중복 변수명이 있습니다: " + ", ".join(duplicate_names))

    return sorted(set(errors)), sorted(set(warnings))


class ValuationEngine:
    """Supplement Table 1/2-compatible KR-2025 valuation engine."""

    def __init__(self, repository: ReferenceRepository) -> None:
        self.repository = repository

    def calculate(
        self,
        metadata: pd.DataFrame,
        dataset_info: DatasetInfo,
    ) -> CalculationOutput:
        df = normalize_metadata_dataframe(
            metadata,
            dataset_info.case_count,
            dataset_info.quality_mode,
        )
        errors, validation_warnings = validate_metadata(
            df, self.repository, dataset_info.quality_mode
        )
        if errors:
            raise ValueError("\n".join(errors))

        df["component_group"] = df["component_detail"].map(component_group_from_detail)
        group_counts = Counter(df["component_group"].tolist())
        examination_count = int(
            (df["component_detail"] == "Examination & Laboratory").sum()
        )

        institute_weight_pct = self.repository.get_institute_weight(dataset_info.institute_code)
        examination_fee_krw = self.repository.get_examination_fee(dataset_info.institute_code)
        management_weight_pct = self.repository.management_weight_pct

        rows: list[dict[str, Any]] = []
        warnings = list(validation_warnings)

        for _, row in df.iterrows():
            detail = str(row["component_detail"])
            group = str(row["component_group"])
            row_warnings: list[str] = []

            total_count = int(row["total_count"])
            non_empty_count = int(row["non_empty_count"])
            accurate_count = int(row["accurate_count"])
            rule_compliant_count = int(row["rule_compliant_count"])
            usable_count = int(row["usable_count"])

            # Step 1 — measurement only. The supplied Supplement Table formula
            # chain does not multiply monetary values by these percentages.
            accuracy_pct = safe_pct(accurate_count, non_empty_count)
            completeness_pct = safe_pct(usable_count, total_count)
            consistency_pct = safe_pct(rule_compliant_count, non_empty_count)
            quality_measurement_basis = (
                "상세 입력값"
                if dataset_info.quality_mode == QUALITY_MODE_DETAILED
                else "간편모드 가정: 정확성·일관성 100%, 완전성=사용가능/전체"
            )

            fee_name_ko = ""
            fee_name_en = ""
            fee_procedure_group = ""
            fee_data_variable = ""
            fee_match_source = ""
            fee_match_score = Decimal("0")

            if group in {"Demographics data", "Questionnaire data", "Dietary data"}:
                count = group_counts[group]
                step2_unit_price = (
                    SURVEY_REFERENCE_FEE_KRW / Decimal(count) if count > 0 else Decimal("0")
                )
                step2_basis = f"{SURVEY_REFERENCE_FEE_KRW:,.0f}원 ÷ {count}개 {group} 변수"
                step2_source = "supplement_group_allocation"
            elif group == "Examination & Laboratory data":
                fee = self.repository.lookup_fee(
                    fee_item=row["medical_fee_item"],
                    manual_unit_price_krw=row["manual_unit_price_krw"],
                    variable_name=row["variable_name"],
                    variable_description=row["variable_description"],
                )
                step2_unit_price = fee.unit_price_krw
                fee_name_ko = fee.fee_name_ko
                fee_name_en = fee.fee_name_en
                fee_procedure_group = fee.procedure_group
                fee_data_variable = fee.data_variable
                fee_match_source = fee.source
                fee_match_score = fee.match_score
                step2_source = fee.source
                step2_basis = (
                    "사용자 직접입력 수가"
                    if fee.source == "manual"
                    else f"Step 2 fee: {fee.fee_name_ko}"
                )
                if fee.warning:
                    row_warnings.append(fee.warning)
            else:
                step2_unit_price = Decimal("0")
                step2_basis = "평가 제외 구성요소"
                step2_source = "not_valued"

            # Step 3 — institution-size weight applied once to the common Step 2
            # fee. This is why the updated Step 2 file has a single `fee` column.
            step3_value = step2_unit_price * (
                Decimal("1") + institute_weight_pct / Decimal("100")
            )

            # Step 4 — institution-specific examination fee is allocated evenly
            # across all Examination & Laboratory variables, as in the workbook.
            if detail == "Examination & Laboratory" and examination_count > 0:
                step4_allocation = examination_fee_krw / Decimal(examination_count)
            else:
                step4_allocation = Decimal("0")
            step4_value = step3_value + step4_allocation

            # Step 5 — original data storage/management factor.
            step5_value = step4_value * (
                Decimal("1") + management_weight_pct / Decimal("100")
            )

            # Step 6 — disease scarcity uses the negative morbidity-derived weight.
            scarcity = self.repository.get_scarcity(row["disease_icd3"])
            if scarcity.warning:
                row_warnings.append(scarcity.warning)
            step6_value = step5_value * (
                Decimal("1") + scarcity.scarcity_weight_pct / Decimal("100")
            )

            # Step 7 — component-level effectiveness score sum/weight.
            effectiveness = self.repository.get_effectiveness(detail)
            effectiveness_weight_pct = effectiveness["effectiveness_weight_pct"]
            step7_unit_value = step6_value * (
                Decimal("1") + effectiveness_weight_pct / Decimal("100")
            )

            final_variable_value = step7_unit_value * Decimal(usable_count)

            warning_text = " | ".join(dict.fromkeys(row_warnings))
            if warning_text:
                warnings.append(f"{row['variable_name']}: {warning_text}")

            rows.append(
                {
                    "variable_name": row["variable_name"],
                    "variable_description": row["variable_description"],
                    "component_detail": detail,
                    "component_group": group,
                    "total_count": total_count,
                    "non_empty_count": non_empty_count,
                    "accurate_count": accurate_count,
                    "rule_compliant_count": rule_compliant_count,
                    "usable_count": usable_count,
                    "not_used_count": int(row["not_used_count"]),
                    "missing_count": int(row["missing_count"]),
                    "quality_mode": dataset_info.quality_mode,
                    "quality_measurement_basis": quality_measurement_basis,
                    "step1_accuracy_pct": float(accuracy_pct) if accuracy_pct is not None else None,
                    "step1_completeness_pct": (
                        float(completeness_pct) if completeness_pct is not None else None
                    ),
                    "step1_consistency_pct": (
                        float(consistency_pct) if consistency_pct is not None else None
                    ),
                    "medical_fee_item": str(row["medical_fee_item"]),
                    "manual_unit_price_krw": float(to_decimal(row["manual_unit_price_krw"])),
                    "fee_name_ko": fee_name_ko,
                    "fee_name_en": fee_name_en,
                    "fee_procedure_group": fee_procedure_group,
                    "fee_data_variable": fee_data_variable,
                    "fee_match_source": fee_match_source,
                    "fee_match_score": float(fee_match_score),
                    "step2_source": step2_source,
                    "step2_basis": step2_basis,
                    "step2_fee_krw": float(step2_unit_price),
                    "step2_unit_price_krw": float(step2_unit_price),
                    "step3_institution_weight_pct": float(institute_weight_pct),
                    "step3_value_krw": float(step3_value),
                    "step4_examination_fee_krw": float(examination_fee_krw),
                    "step4_examination_variable_count": examination_count,
                    "step4_examination_allocation_krw": float(step4_allocation),
                    "step4_value_krw": float(step4_value),
                    "step5_management_weight_pct": float(management_weight_pct),
                    "step5_value_krw": float(step5_value),
                    "disease_icd3": scarcity.icd3,
                    "disease_name": scarcity.disease_name,
                    "disease_patient_count": scarcity.patient_count,
                    "morbidity_pct": (
                        float(scarcity.morbidity_pct)
                        if scarcity.morbidity_pct is not None
                        else None
                    ),
                    "morbidity_group": scarcity.morbidity_group,
                    "scarcity_weight_pct": float(scarcity.scarcity_weight_pct),
                    "step6_value_krw": float(step6_value),
                    "research_score": float(effectiveness["research_score"]),
                    "clinical_public_health_score": float(
                        effectiveness["clinical_public_health_score"]
                    ),
                    "policy_score": float(effectiveness["policy_score"]),
                    "industry_ai_score": float(effectiveness["industry_ai_score"]),
                    "effectiveness_weight_pct": float(effectiveness_weight_pct),
                    "step7_unit_value_krw": float(step7_unit_value),
                    "final_variable_value_krw": float(final_variable_value),
                    "warning": warning_text,
                }
            )

        return CalculationOutput(rows=rows, warnings=sorted(set(warnings)))


def _mean_numeric(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.mean())


def summarize_results(result_df: pd.DataFrame) -> dict[str, Any]:
    if result_df is None or result_df.empty:
        return {
            "total_value_krw": 0.0,
            "variable_count": 0,
            "total_usable_count": 0,
            "examination_variable_count": 0,
            "disease_linked_count": 0,
            "scarcity_applied_count": 0,
            "average_effectiveness_pct": 0.0,
            "average_accuracy_pct": None,
            "average_completeness_pct": None,
            "average_consistency_pct": None,
            "component_summary": pd.DataFrame(),
            "top5": pd.DataFrame(),
        }

    component_summary = (
        result_df.groupby("component_detail", as_index=False)
        .agg(
            variable_count=("variable_name", "count"),
            usable_count=("usable_count", "sum"),
            final_variable_value_krw=("final_variable_value_krw", "sum"),
        )
        .sort_values("final_variable_value_krw", ascending=False)
    )
    top5 = result_df.nlargest(5, "final_variable_value_krw").copy()

    return {
        "total_value_krw": float(result_df["final_variable_value_krw"].sum()),
        "variable_count": int(len(result_df)),
        "total_usable_count": int(result_df["usable_count"].sum()),
        "examination_variable_count": int(
            (result_df["component_detail"] == "Examination & Laboratory").sum()
        ),
        "disease_linked_count": int(result_df["disease_icd3"].astype(bool).sum()),
        "scarcity_applied_count": int((result_df["scarcity_weight_pct"] != 0).sum()),
        "average_effectiveness_pct": float(result_df["effectiveness_weight_pct"].mean()),
        "average_accuracy_pct": _mean_numeric(result_df["step1_accuracy_pct"]),
        "average_completeness_pct": _mean_numeric(result_df["step1_completeness_pct"]),
        "average_consistency_pct": _mean_numeric(result_df["step1_consistency_pct"]),
        "component_summary": component_summary,
        "top5": top5,
    }
