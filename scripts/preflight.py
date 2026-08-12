from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ts26040_app.exports import (  # noqa: E402
    build_csv_bytes,
    build_excel_bytes,
    build_html_report,
    build_json_bytes,
)
from ts26040_app.identity import load_service_identity  # noqa: E402
from ts26040_app.models import DatasetInfo  # noqa: E402
from ts26040_app.references import ReferenceRepository  # noqa: E402
from ts26040_app.storage import ResultStore  # noqa: E402
from ts26040_app.valuation import ValuationEngine, summarize_results  # noqa: E402

EXPECTED_REFERENCE_HASHES = {
    "step2_medical_unit_fee.csv": "177158ea548b54c2cbe4df6e470d792a1b987a3b6fcb569174a58e6f3a42f356",
    "step3_institue_size.csv": "a3a966ff999ab92aca23c8d2a5ea7e562e49a130b00a5869f188b4e757444d76",
    "step4_examination_fee_kr2025.csv": "684af12856957dc4d3a07c0bce67257f1dcee86dffb63c440c7807fd6f6852ee",
    "step5_data_management_cost.csv": "f40858b4c0fa6298e1682064317b4376e2afbd117237490a17dbccc9959de740",
    "step6_disease_scarcity_kr2025.csv": "ac1f9bf50c4186a486219cc781317508654182ecad8c6bdbadf06d06dd944569",
    "step7_component_reference.csv": "493380289808c8ad7309a3d91c236bf3ec9b1d315fa872fc0cb6f98dd0724565",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _demo_metadata() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "variable_name": "Sex",
                "variable_description": "성별",
                "component_detail": "Demographics",
                "total_count": 1000,
                "usable_count": 1000,
                "disease_icd3": "",
                "medical_fee_item": "",
                "manual_unit_price_krw": 0,
            },
            {
                "variable_name": "Age",
                "variable_description": "나이",
                "component_detail": "Demographics",
                "total_count": 1000,
                "usable_count": 1000,
                "disease_icd3": "",
                "medical_fee_item": "",
                "manual_unit_price_krw": 0,
            },
            {
                "variable_name": "Smoking",
                "variable_description": "흡연 여부",
                "component_detail": "Health Behavior",
                "total_count": 1000,
                "usable_count": 850,
                "disease_icd3": "",
                "medical_fee_item": "",
                "manual_unit_price_krw": 0,
            },
            {
                "variable_name": "TG",
                "variable_description": "중성지방",
                "component_detail": "Examination & Laboratory",
                "total_count": 1000,
                "usable_count": 700,
                "disease_icd3": "E78",
                "medical_fee_item": "트리글리세라이드",
                "manual_unit_price_krw": 0,
            },
            {
                "variable_name": "HbA1c",
                "variable_description": "당화혈색소",
                "component_detail": "Examination & Laboratory",
                "total_count": 1000,
                "usable_count": 1000,
                "disease_icd3": "E11",
                "medical_fee_item": "헤모글로빈 A1c",
                "manual_unit_price_krw": 0,
            },
        ]
    )


def run_preflight() -> dict[str, object]:
    data_dir = PROJECT_ROOT / "data"
    actual_hashes = {
        name: _sha256(data_dir / name) for name in EXPECTED_REFERENCE_HASHES
    }
    if actual_hashes != EXPECTED_REFERENCE_HASHES:
        raise AssertionError(
            "Reference hash mismatch:\n"
            + json.dumps(actual_hashes, ensure_ascii=False, indent=2)
        )

    repository = ReferenceRepository()
    dataset_info = DatasetInfo(
        dataset_name="당뇨병 정형 임상 데이터셋",
        evaluation_year=2025,
        institute_code="general-hospital_mid-tier",
        case_count=1000,
    )
    output = ValuationEngine(repository).calculate(_demo_metadata(), dataset_info)
    result_df = pd.DataFrame(output.rows)
    summary = summarize_results(result_df)

    assert summary["variable_count"] == 5
    assert summary["total_usable_count"] == 4550
    assert abs(float(summary["average_completeness_pct"]) - 91.0) < 1e-9
    assert abs(float(summary["total_value_krw"]) - 25455441.375) < 1e-6
    assert not output.warnings

    identity = load_service_identity()
    exports = {
        "csv": build_csv_bytes(result_df),
        "excel": build_excel_bytes(
            dataset_info,
            result_df,
            summary,
            repository.manifest(),
            output.warnings,
            identity=identity,
        ),
        "html": build_html_report(
            dataset_info, result_df, summary, output.warnings, identity=identity
        ),
        "json": build_json_bytes(
            dataset_info, result_df, summary, output.warnings, identity=identity
        ),
    }
    if not all(exports.values()):
        raise AssertionError("One or more export payloads are empty.")
    if identity.operator_name.encode("utf-8") not in exports["html"]:
        raise AssertionError("HTML report is missing operator identity.")

    with tempfile.TemporaryDirectory() as temporary_directory:
        database_path = Path(temporary_directory) / "preflight.sqlite3"
        store = ResultStore(f"sqlite:///{database_path.as_posix()}")
        run_id = store.save(
            dataset_info, result_df, summary, output.warnings
        )
        recent = store.list_recent(limit=5)
        if not recent or recent[0]["run_id"] != run_id:
            raise AssertionError("SQLite save/list smoke test failed.")

    return {
        "status": "PASS",
        "reference_hashes": actual_hashes,
        "reference_rows": {
            item["step"]: item["rows"] for item in repository.manifest()
        },
        "production_demo": {
            "variable_count": summary["variable_count"],
            "total_usable_count": summary["total_usable_count"],
            "average_completeness_pct": summary["average_completeness_pct"],
            "total_value_krw": summary["total_value_krw"],
            "warnings": output.warnings,
        },
        "export_bytes": {name: len(payload) for name, payload in exports.items()},
        "sqlite_save_list": "PASS",
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2))
