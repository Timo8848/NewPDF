from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List

from idp.postprocess.normalizers import normalize_amount, normalize_date


@dataclass
class ValidationMessage:
    field: str
    message: str
    level: str = "error"


@dataclass
class ValidationSummary:
    errors: List[ValidationMessage]
    warnings: List[ValidationMessage]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def regex_validations(fields: Dict[str, str]) -> List[ValidationMessage]:
    rules = {
        "invoice_number": r"^INV[- ]?[0-9A-Za-z]+$",
        "tax_id": r"^[0-9A-Za-z-]{9,15}$",
        "routing_number": r"^[0-9]{9}$",
        "bank_account": r"^[0-9]{6,20}$",
        "id_number": r"^[0-9A-Za-z-]+$",
    }
    messages: List[ValidationMessage] = []
    for field, pattern in rules.items():
        value = fields.get(field)
        if not value:
            continue
        if not re.match(pattern, str(value)):
            messages.append(ValidationMessage(field=field, message="Regex validation failed"))
    return messages


def cross_field_checks(fields: Dict[str, str]) -> List[ValidationMessage]:
    messages: List[ValidationMessage] = []
    subtotal = normalize_amount(fields.get("subtotal_amount"))
    tax = normalize_amount(fields.get("tax_amount"))
    total = normalize_amount(fields.get("total_amount"))
    if subtotal is not None and tax is not None and total is not None:
        if subtotal + tax != total:
            messages.append(
                ValidationMessage(
                    field="total_amount",
                    message=f"subtotal ({subtotal}) + tax ({tax}) != total ({total})",
                )
            )
    invoice_date = normalize_date(fields.get("invoice_date"))
    due_date = normalize_date(fields.get("due_date"))
    if invoice_date and due_date and invoice_date > due_date:
        messages.append(
            ValidationMessage(field="due_date", message="Due date earlier than invoice date", level="warning")
        )
    expiry = normalize_date(fields.get("expiry_date"))
    birth = normalize_date(fields.get("birth_date"))
    if expiry and birth and expiry < birth:
        messages.append(ValidationMessage(field="expiry_date", message="Expiry date earlier than birth date"))
    return messages


def validate_fields(fields: Dict[str, str]) -> ValidationSummary:
    errors = regex_validations(fields)
    errors.extend([m for m in cross_field_checks(fields) if m.level == "error"])
    warnings = [m for m in cross_field_checks(fields) if m.level == "warning"]
    return ValidationSummary(errors=errors, warnings=warnings)
