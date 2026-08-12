from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median
from typing import Any

from .config import (
    INSTITUTE_CODE_ALIASES,
    NON_VALUED_COMPONENT,
    REFERENCE_PATHS,
    ReferencePaths,
)
from .models import FeeLookupResult, ScarcityLookupResult


def _decimal(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return Decimal(default)
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal(default)


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return default


def _normalize_institute_code(value: str) -> str:
    code = str(value or "").strip()
    return INSTITUTE_CODE_ALIASES.get(code, code)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _normalized_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def _search_tokens(value: str) -> list[str]:
    raw = [value]
    raw.extend(re.split(r"[;,/|]", value or ""))
    output: list[str] = []
    for item in raw:
        normalized = _normalized_text(item)
        if normalized and normalized not in output:
            output.append(normalized)
    return output


class ReferenceRepository:
    """Load and validate Step 2–7 CSV references.

    Step 2 is intentionally a curated 103-row catalog. The supplied ``fee``
    column is the base medical-procedure unit price. Institution-size effects
    are applied once, in Step 3, which avoids the previous double-counting risk
    created by institution-specific price columns in Step 2.
    """

    STEP2_REQUIRED_COLUMNS = {
        "fee_name_ko",
        "fee_name_en",
        "procedure_group",
        "data_variable",
        "fee",
    }

    def __init__(self, paths: ReferencePaths = REFERENCE_PATHS, **_: Any) -> None:
        self.paths = paths
        self._validate_paths()
        self._step2 = self._load_step2()
        self._step3 = self._load_step3()
        self._step4 = self._load_step4()
        self._step5 = self._load_step5()
        self._step6 = self._load_step6()
        self._step7 = self._load_step7()
        self._manifest_cache = self._build_manifest()

    def _validate_paths(self) -> None:
        missing = [
            str(path)
            for path in asdict(self.paths).values()
            if not Path(path).exists()
        ]
        if missing:
            raise FileNotFoundError(
                "Required reference files are missing: " + ", ".join(missing)
            )

    def _load_step2(self) -> list[dict[str, Any]]:
        rows = _read_csv_rows(self.paths.step2)
        if not rows:
            raise ValueError("Step 2 medical unit fee reference is empty.")
        columns = set(rows[0])
        missing = sorted(self.STEP2_REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError(
                "Step 2 CSV is missing required columns: " + ", ".join(missing)
            )

        output: list[dict[str, Any]] = []
        seen_ko: set[str] = set()
        for position, row in enumerate(rows, start=1):
            fee_name_ko = str(row.get("fee_name_ko", "")).strip()
            fee_name_en = str(row.get("fee_name_en", "")).strip()
            procedure_group = str(row.get("procedure_group", "")).strip()
            data_variable = str(row.get("data_variable", "")).strip()
            fee = _decimal(row.get("fee"))
            if not all([fee_name_ko, fee_name_en, procedure_group, data_variable]):
                raise ValueError(f"Step 2 row {position} contains a blank required value.")
            if fee <= 0:
                raise ValueError(f"Step 2 row {position} has a non-positive fee.")
            if fee_name_ko in seen_ko:
                raise ValueError(f"Duplicate Step 2 fee_name_ko: {fee_name_ko}")
            seen_ko.add(fee_name_ko)

            tokens: list[str] = []
            for value in [fee_name_ko, fee_name_en, procedure_group, data_variable]:
                for token in _search_tokens(value):
                    if token not in tokens:
                        tokens.append(token)

            output.append(
                {
                    "catalog_order": position,
                    "fee_name_ko": fee_name_ko,
                    "fee_name_en": fee_name_en,
                    "procedure_group": procedure_group,
                    "data_variable": data_variable,
                    "fee": fee,
                    "_tokens": tuple(tokens),
                }
            )
        return output

    def _load_step3(self) -> dict[str, Decimal]:
        rows = _read_csv_rows(self.paths.step3)
        output: dict[str, Decimal] = {}
        for row in rows:
            code = _normalize_institute_code(row.get("institute_size", ""))
            if code:
                output[code] = _decimal(
                    row.get("institute_size_weigth", row.get("institute_size_weight"))
                )
        if not output:
            raise ValueError("Step 3 institution-size reference is empty.")
        return output

    def _load_step4(self) -> dict[str, Decimal]:
        rows = _read_csv_rows(self.paths.step4)
        output: dict[str, Decimal] = {}
        for row in rows:
            code = _normalize_institute_code(
                row.get("institute_size_examination", "")
            )
            if code:
                output[code] = _decimal(row.get("examination_fee"))
        if not output:
            raise ValueError("Step 4 examination-fee reference is empty.")
        return output

    def _load_step5(self) -> Decimal:
        rows = _read_csv_rows(self.paths.step5)
        if not rows:
            raise ValueError("Step 5 data-management reference is empty.")
        return _decimal(
            rows[0].get("data_management_weigth", rows[0].get("data_management_weight"))
        )

    def _load_step6(self) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for row in _read_csv_rows(self.paths.step6):
            code = str(row.get("icd3", "")).strip().upper()
            if not code:
                continue
            output[code] = {
                "ranking": _integer(row.get("ranking")),
                "icd3": code,
                "disease_name": str(row.get("disease_name", "")).strip(),
                "patient_count": _integer(row.get("patient_count")),
                "morbidity_pct": _decimal(row.get("morbidity_pct")),
                "morbidity_group": str(row.get("morbidity_group", "")).strip(),
                "scarcity_weight_pct": _decimal(row.get("scarcity_weight_pct")),
            }
        if not output:
            raise ValueError("Step 6 disease-scarcity reference is empty.")
        return output

    def _load_step7(self) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for row in _read_csv_rows(self.paths.step7):
            detail = str(row.get("component_detail", "")).strip()
            if not detail:
                continue
            output[detail] = {
                "component_code": _integer(row.get("component_code")),
                "component_detail": detail,
                "research_score": _decimal(row.get("research_score")),
                "clinical_public_health_score": _decimal(
                    row.get("clinical_public_health_score")
                ),
                "policy_score": _decimal(row.get("policy_score")),
                "industry_ai_score": _decimal(row.get("industry_ai_score")),
                "effectiveness_weight_pct": _decimal(
                    row.get("effectiveness_weight")
                ),
            }
        output[NON_VALUED_COMPONENT] = {
            "component_code": 99,
            "component_detail": NON_VALUED_COMPONENT,
            "research_score": Decimal("0"),
            "clinical_public_health_score": Decimal("0"),
            "policy_score": Decimal("0"),
            "industry_ai_score": Decimal("0"),
            "effectiveness_weight_pct": Decimal("0"),
        }
        return output

    @property
    def component_details(self) -> list[str]:
        return [
            detail
            for detail, row in sorted(
                self._step7.items(), key=lambda item: item[1]["component_code"]
            )
        ]

    @property
    def fee_item_labels(self) -> list[str]:
        return [row["fee_name_ko"] for row in self._step2]

    def get_institute_weight(self, institute_code: str) -> Decimal:
        code = _normalize_institute_code(institute_code)
        try:
            return self._step3[code]
        except KeyError as exc:
            raise KeyError(f"Step 3 institution code not found: {code}") from exc

    def get_examination_fee(self, institute_code: str) -> Decimal:
        code = _normalize_institute_code(institute_code)
        try:
            return self._step4[code]
        except KeyError as exc:
            raise KeyError(f"Step 4 institution code not found: {code}") from exc

    @property
    def management_weight_pct(self) -> Decimal:
        return self._step5

    def get_effectiveness(self, component_detail: str) -> dict[str, Any]:
        return self._step7.get(
            component_detail,
            {
                "component_code": 0,
                "component_detail": component_detail,
                "research_score": Decimal("0"),
                "clinical_public_health_score": Decimal("0"),
                "policy_score": Decimal("0"),
                "industry_ai_score": Decimal("0"),
                "effectiveness_weight_pct": Decimal("0"),
            },
        )

    def get_scarcity(self, icd3: str) -> ScarcityLookupResult:
        code = str(icd3 or "").strip().upper()
        if not code:
            return ScarcityLookupResult()
        row = self._step6.get(code)
        if row is None:
            return ScarcityLookupResult(
                icd3=code,
                warning=(
                    f"ICD-3 {code} was not found in the Step 6 reference; "
                    "0% scarcity weight was applied."
                ),
            )
        return ScarcityLookupResult(
            icd3=code,
            disease_name=row["disease_name"],
            patient_count=row["patient_count"],
            morbidity_pct=row["morbidity_pct"],
            morbidity_group=row["morbidity_group"],
            scarcity_weight_pct=row["scarcity_weight_pct"],
        )

    def _row_to_fee_result(
        self,
        row: dict[str, Any],
        *,
        source: str,
        matched_query: str,
        match_score: Decimal = Decimal("100"),
        warning: str = "",
    ) -> FeeLookupResult:
        return FeeLookupResult(
            unit_price_krw=row["fee"],
            fee_name_ko=row["fee_name_ko"],
            fee_name_en=row["fee_name_en"],
            procedure_group=row["procedure_group"],
            data_variable=row["data_variable"],
            source=source,
            matched_query=matched_query,
            match_score=match_score,
            warning=warning,
        )

    def _exact_fee_rows(self, query: str) -> list[dict[str, Any]]:
        normalized = _normalized_text(query)
        if not normalized:
            return []
        return [row for row in self._step2 if normalized in row["_tokens"]]

    def lookup_fee(
        self,
        fee_item: str = "",
        manual_unit_price_krw: Any = 0,
        variable_name: str = "",
        variable_description: str = "",
        **_: Any,
    ) -> FeeLookupResult:
        """Resolve a Step 2 fee.

        Exact matching is allowed against Korean/English fee names and the
        semicolon-delimited ``data_variable`` tokens. Fuzzy suggestions are
        never silently applied during valuation; they are exposed separately by
        :meth:`suggest_fees` so the user can confirm the mapping.
        """

        manual = _decimal(manual_unit_price_krw)
        if manual > 0:
            return FeeLookupResult(
                unit_price_krw=manual,
                fee_name_ko="사용자 직접입력 수가",
                source="manual",
                matched_query=str(fee_item or variable_name or variable_description),
                match_score=Decimal("100"),
            )

        query = str(fee_item or "").strip()
        if query:
            rows = self._exact_fee_rows(query)
            if len(rows) == 1:
                return self._row_to_fee_result(
                    rows[0], source="step2_csv", matched_query=query
                )
            if len(rows) > 1:
                return FeeLookupResult(
                    unit_price_krw=Decimal("0"),
                    source="ambiguous",
                    matched_query=query,
                    warning=f"Step 2 의료행위 '{query}'가 여러 항목과 일치합니다.",
                )
            return FeeLookupResult(
                unit_price_krw=Decimal("0"),
                source="not_found",
                matched_query=query,
                warning=f"Step 2 의료행위 '{query}'를 참조표에서 찾지 못했습니다.",
            )

        # Conservative exact auto-mapping for compact uploads. It only runs when
        # a variable name or description exactly matches one catalog token.
        for candidate in [variable_name, variable_description]:
            rows = self._exact_fee_rows(candidate)
            if len(rows) == 1:
                return self._row_to_fee_result(
                    rows[0], source="exact_auto_match", matched_query=str(candidate)
                )

        return FeeLookupResult(
            unit_price_krw=Decimal("0"),
            source="unmapped",
            warning=(
                "Step 2 의료행위가 선택되지 않았습니다. 의료행위 항목을 선택하거나 "
                "직접입력 수가를 입력하십시오."
            ),
        )

    def suggest_fees(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        normalized = _normalized_text(query)
        if not normalized:
            return []
        limit = max(1, min(int(limit), 100))
        candidates: list[tuple[float, dict[str, Any]]] = []
        for row in self._step2:
            token_scores: list[float] = []
            for token in row["_tokens"]:
                if normalized == token:
                    score = 100.0
                elif normalized in token or token in normalized:
                    length_ratio = min(len(normalized), len(token)) / max(
                        len(normalized), len(token)
                    )
                    score = 90.0 + 8.0 * length_ratio
                else:
                    score = 100.0 * SequenceMatcher(None, normalized, token).ratio()
                token_scores.append(score)
            score = max(token_scores or [0.0])
            if score >= 35.0:
                candidates.append((score, row))
        candidates.sort(key=lambda item: (-item[0], item[1]["catalog_order"]))
        return [
            {
                "match_score": round(score, 1),
                "fee_name_ko": row["fee_name_ko"],
                "fee_name_en": row["fee_name_en"],
                "procedure_group": row["procedure_group"],
                "data_variable": row["data_variable"],
                "fee": float(row["fee"]),
            }
            for score, row in candidates[:limit]
        ]

    def best_fee_suggestion(
        self,
        variable_name: str,
        variable_description: str = "",
        minimum_score: float = 82.0,
    ) -> dict[str, Any] | None:
        query = " ".join(
            item for item in [str(variable_name).strip(), str(variable_description).strip()] if item
        )
        suggestions = self.suggest_fees(query, limit=2)
        if not suggestions:
            return None
        first = suggestions[0]
        second_score = suggestions[1]["match_score"] if len(suggestions) > 1 else 0.0
        # Require both a high score and a clear margin to avoid silent ambiguous
        # mappings in medical terminology.
        if first["match_score"] >= minimum_score and first["match_score"] - second_score >= 5.0:
            return first
        return None

    def search_fees(self, keyword: str, limit: int = 100) -> list[dict[str, Any]]:
        term = _normalized_text(keyword)
        limit = max(1, min(int(limit), 500))
        rows: list[dict[str, Any]] = []
        for row in self._step2:
            if term and not any(term in token for token in row["_tokens"]):
                continue
            rows.append(
                {
                    "fee_name_ko": row["fee_name_ko"],
                    "fee_name_en": row["fee_name_en"],
                    "procedure_group": row["procedure_group"],
                    "data_variable": row["data_variable"],
                    "fee": float(row["fee"]),
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def fee_catalog_summary(self) -> dict[str, Any]:
        fees = [float(row["fee"]) for row in self._step2]
        groups: dict[str, int] = {}
        for row in self._step2:
            groups[row["procedure_group"]] = groups.get(row["procedure_group"], 0) + 1
        return {
            "total_rows": len(self._step2),
            "procedure_groups": [
                {"procedure_group": key, "row_count": value}
                for key, value in sorted(groups.items(), key=lambda item: (-item[1], item[0]))
            ],
            "minimum_fee_krw": min(fees),
            "median_fee_krw": median(fees),
            "maximum_fee_krw": max(fees),
        }

    def search_diseases(self, keyword: str, limit: int = 300) -> list[dict[str, Any]]:
        term = str(keyword or "").strip().casefold()
        rows = sorted(self._step6.values(), key=lambda row: row["ranking"])
        if term:
            rows = [
                row
                for row in rows
                if term in row["icd3"].casefold()
                or term in row["disease_name"].casefold()
            ]
        return [
            {
                **row,
                "morbidity_pct": float(row["morbidity_pct"]),
                "scarcity_weight_pct": float(row["scarcity_weight_pct"]),
            }
            for row in rows[: max(1, min(int(limit), 2000))]
        ]

    def step3_table(self) -> list[dict[str, Any]]:
        return [
            {"institute_code": key, "institute_size_weight_pct": float(value)}
            for key, value in self._step3.items()
        ]

    def step4_table(self) -> list[dict[str, Any]]:
        return [
            {"institute_code": key, "examination_fee_krw": float(value)}
            for key, value in self._step4.items()
        ]

    def step5_table(self) -> list[dict[str, Any]]:
        return [
            {
                "data_management_cost": "management_factor",
                "data_management_weight_pct": float(self._step5),
            }
        ]

    def step7_table(self) -> list[dict[str, Any]]:
        return [
            {
                **row,
                "research_score": float(row["research_score"]),
                "clinical_public_health_score": float(
                    row["clinical_public_health_score"]
                ),
                "policy_score": float(row["policy_score"]),
                "industry_ai_score": float(row["industry_ai_score"]),
                "effectiveness_weight_pct": float(row["effectiveness_weight_pct"]),
            }
            for _, row in sorted(
                self._step7.items(), key=lambda item: item[1]["component_code"]
            )
        ]

    def _build_manifest(self) -> list[dict[str, Any]]:
        manifest: list[dict[str, Any]] = []
        for step, path in [
            ("STEP2", self.paths.step2),
            ("STEP3", self.paths.step3),
            ("STEP4", self.paths.step4),
            ("STEP5", self.paths.step5),
            ("STEP6", self.paths.step6),
            ("STEP7", self.paths.step7),
        ]:
            with path.open("rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            rows = len(_read_csv_rows(path))
            manifest.append(
                {
                    "step": step,
                    "file": path.name,
                    "rows": rows,
                    "bytes": path.stat().st_size,
                    "sha256": digest,
                }
            )
        return manifest

    def manifest(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._manifest_cache]
