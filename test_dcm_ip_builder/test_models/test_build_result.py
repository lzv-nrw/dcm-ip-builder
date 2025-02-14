"""BuildResult-data model test-module."""

from pathlib import Path

from dcm_common.models.data_model import get_model_serialization_test

from dcm_ip_builder.models import BuildResult


test_build_result_json = get_model_serialization_test(
    BuildResult, (
        ((), {}),
        ((), {"path": Path(".")}),
        (
            (),
            {"success": True, "path": Path(".")},
        ),
    )
)
