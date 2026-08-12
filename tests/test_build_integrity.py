from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ts26040_app.references import ReferenceRepository


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_REFERENCE_HASHES = {
    "step2_medical_unit_fee.csv": "177158ea548b54c2cbe4df6e470d792a1b987a3b6fcb569174a58e6f3a42f356",
    "step3_institue_size.csv": "a3a966ff999ab92aca23c8d2a5ea7e562e49a130b00a5869f188b4e757444d76",
    "step4_examination_fee_kr2025.csv": "684af12856957dc4d3a07c0bce67257f1dcee86dffb63c440c7807fd6f6852ee",
    "step5_data_management_cost.csv": "f40858b4c0fa6298e1682064317b4376e2afbd117237490a17dbccc9959de740",
    "step6_disease_scarcity_kr2025.csv": "ac1f9bf50c4186a486219cc781317508654182ecad8c6bdbadf06d06dd944569",
    "step7_component_reference.csv": "493380289808c8ad7309a3d91c236bf3ec9b1d315fa872fc0cb6f98dd0724565",
}
EXPECTED_SOURCE_HASHES = {
    "context_reference.docx": "fbe9840b69285c9a6bc1f05edfccd5235d192f5abe3cd8a7d868737ace0b2768",
    "Supplements_Table_1_reference.xlsx": "04e36372a2db944a427680549cd43e9ae13cd56dffeba1d082b2559b43fe1821",
    "Supplements_Table_2_KR2022_reference.xlsx": "dc78fc1ab0369c6274af17154a745aad1b7eefa2a8f15e7b2b20dd64223e006f",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_uploaded_reference_csv_hashes_and_manifest_are_locked():
    data_dir = PROJECT_ROOT / "data"
    actual = {
        name: _sha256(data_dir / name) for name in EXPECTED_REFERENCE_HASHES
    }
    assert actual == EXPECTED_REFERENCE_HASHES

    runtime_manifest = {
        item["file"]: (item["rows"], item["sha256"])
        for item in ReferenceRepository().manifest()
    }
    static_manifest = {
        Path(item["path"]).name: (item["rows"], item["sha256"])
        for item in json.loads(
            (data_dir / "reference_manifest.json").read_text(encoding="utf-8")
        )
    }
    assert runtime_manifest == static_manifest


def test_context_and_supplement_source_files_are_preserved_exactly():
    docs_dir = PROJECT_ROOT / "docs"
    actual = {name: _sha256(docs_dir / name) for name in EXPECTED_SOURCE_HASHES}
    assert actual == EXPECTED_SOURCE_HASHES


def test_github_streamlit_deployment_scaffold_is_present_and_secret_safe():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8"
    )
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "actions/checkout@v7" in workflow
    assert "actions/setup-python@v7" in workflow
    assert 'python-version: "3.12"' in workflow
    assert "python scripts/preflight.py" in workflow
    assert ".streamlit/secrets.toml" in gitignore
    assert not (PROJECT_ROOT / ".streamlit" / "secrets.toml").exists()
    assert "streamlit" in requirements
    assert (PROJECT_ROOT / "app.py").exists()
