from idp.postprocess.validators import validate_fields


def test_validate_fields_totals_match():
    summary = validate_fields(
        {
            "subtotal_amount": "100.00",
            "tax_amount": "10.00",
            "total_amount": "110.00",
            "invoice_number": "INV-123",
        }
    )
    assert summary.is_valid


def test_validate_fields_detects_mismatch():
    summary = validate_fields(
        {
            "subtotal_amount": "100.00",
            "tax_amount": "10.00",
            "total_amount": "111.00",
            "invoice_number": "INV-123",
        }
    )
    assert not summary.is_valid
    assert any(msg.field == "total_amount" for msg in summary.errors)
