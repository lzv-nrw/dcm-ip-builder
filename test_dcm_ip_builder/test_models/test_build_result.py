"""BuildResult-data model test-module."""

from pathlib import Path

from dcm_common.models.data_model import get_model_serialization_test

from dcm_ip_builder.models import BuildResult
from dcm_ip_builder.plugins.validation import ValidationPluginResult


test_build_result_json = get_model_serialization_test(
    BuildResult,
    (
        ((), {}),
        (
            (),
            {
                "path": Path("."),
                "success": True,
                "valid": True,
                "source_organization": "c",
                "origin_system_id": "a",
                "external_id": "b",
                "baginfo_metadata": {"d": ["1", "2"]},
                "details": {"0": ValidationPluginResult()},
            },
        ),
    ),
)
