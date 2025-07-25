"""ValidationResult-data model test-module."""

from dcm_common.models.data_model import get_model_serialization_test

from dcm_ip_builder.models import ValidationResult
from dcm_ip_builder.plugins.validation.interface import ValidationPluginResult


test_validation_result_json = get_model_serialization_test(
    ValidationResult,
    (
        ((), {}),
        (
            (),
            {
                "success": True,
                "valid": True,
                "origin_system_id": "a",
                "external_id": "b",
                "details": {"0": ValidationPluginResult()},
            },
        ),
    ),
)
