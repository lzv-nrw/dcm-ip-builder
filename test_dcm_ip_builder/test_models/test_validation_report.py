"""ValidationReport-data model test-module."""

from dcm_common.models import Token, Report as BaseReport
from dcm_common.models.data_model import get_model_serialization_test

from dcm_ip_builder.models import ValidationReport, ValidationResult


test_report_json = get_model_serialization_test(
    ValidationReport, (
        ((), {"host": ""}),
        ((), {
            "host": "", "token": Token(), "args": {"arg": "value"},
            "data": ValidationResult(
                logid="0@native"
            )
        }),
        ((), {
            "host": "", "children": {
                "test": BaseReport(host="sub-report").json
            }
        }),
    )
)
