from decimal import Decimal


def test_single_fee_lookup_is_institution_neutral(reference_repository):
    clinic = reference_repository.lookup_fee(fee_item="헤모글로빈 A1c")
    tertiary = reference_repository.lookup_fee(fee_item="헤모글로빈 A1c")
    assert clinic.unit_price_krw == Decimal("3440")
    assert tertiary.unit_price_krw == Decimal("3440")


def test_exact_variable_token_lookup(reference_repository):
    result = reference_repository.lookup_fee(variable_name="HbA1c")
    assert result.unit_price_krw == Decimal("3440")
    assert result.source == "exact_auto_match"


def test_manual_fee_override(reference_repository):
    result = reference_repository.lookup_fee(
        fee_item="헤모글로빈 A1c", manual_unit_price_krw=9999
    )
    assert result.unit_price_krw == Decimal("9999")
    assert result.source == "manual"


def test_scarcity_lookup(reference_repository):
    result = reference_repository.get_scarcity("e11")
    assert result.icd3 == "E11"
    assert result.scarcity_weight_pct == Decimal("-80")
