"""BuildReport-data model test-module."""

from pathlib import Path

from dcm_common.models import Token
from dcm_common.models.data_model import get_model_serialization_test

from dcm_ip_builder.models import BuildReport, BuildResult


test_report_json = get_model_serialization_test(
    BuildReport, (
        ((), {"host": ""}),
        ((), {
            "host": "", "token": Token(), "args": {"arg": "value"},
            "data": BuildResult(
                path=Path(".")
            )
        }),
    )
)
