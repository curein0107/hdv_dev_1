from __future__ import annotations

import csv
import hashlib
from decimal import Decimal
from pathlib import Path

from ts26040_app.references import ReferenceRepository


def test_production_fee_catalog_schema_and_counts():
    fee_path = Path(__file__).resolve().parents[1] / "data" / "step2_medical_unit_fee.csv"
    with fee_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    required = {"fee_name_ko", "fee_name_en", "procedure_group", "data_variable", "fee"}
    assert rows
    assert set(rows[0]) == required
    assert len(rows) == 103
    assert len({row["fee_name_ko"] for row in rows}) == 103
    assert len({row["procedure_group"] for row in rows}) == 19
    assert all(float(row["fee"]) > 0 for row in rows)
    assert "hospital_base_before_addon_krw" not in rows[0]
    assert hashlib.sha256(fee_path.read_bytes()).hexdigest() == "177158ea548b54c2cbe4df6e470d792a1b987a3b6fcb569174a58e6f3a42f356"


def test_production_fee_catalog_lookup_and_search():
    repository = ReferenceRepository()

    hba1c = repository.lookup_fee(fee_item="헤모글로빈 A1c")
    assert hba1c.unit_price_krw == Decimal("7350")
    assert hba1c.source == "step2_csv"

    # Step 2 fee is institution-neutral; the institution effect belongs to Step 3.
    assert repository.get_institute_weight("clinic_small-micro") == Decimal("15")
    assert repository.get_institute_weight("teritary-hospital_large") == Decimal("30")

    results = repository.search_fees("연속혈당", limit=20)
    assert len(results) >= 3
    assert all("fee" in row for row in results)


def test_fee_catalog_summary_is_reproducible():
    summary = ReferenceRepository().fee_catalog_summary()
    assert summary["total_rows"] == 103
    assert len(summary["procedure_groups"]) == 19
    assert summary["minimum_fee_krw"] == 850
    assert summary["median_fee_krw"] == 10740
    assert summary["maximum_fee_krw"] == 488290
