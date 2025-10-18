"""ValidationReport-data model test-module."""

from dcm_common.orchestra import Token
from dcm_common.models.data_model import get_model_serialization_test

from dcm_ip_builder.models import ValidationReport, ValidationResult


test_report_json = get_model_serialization_test(
    ValidationReport, (
        ((), {"host": ""}),
        ((), {
            "host": "", "token": Token("0"), "args": {"arg": "value"},
            "data": ValidationResult()
        }),
    )
)
