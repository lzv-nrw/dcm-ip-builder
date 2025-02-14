"""Test module for the `ValidationConfig` data model."""

from pathlib import Path
from dcm_common.models.data_model import get_model_serialization_test

from dcm_ip_builder.models import Target, ValidationConfig


test_validation_config_json = get_model_serialization_test(
    ValidationConfig, (
        (
            (Target(Path(".")),), {}
        ),
        (
            (Target(Path(".")), "bagit_profile_url", "payload_profile_url"), {}
        ),
        (
            (), {"target": Target(Path("."))}
        ),
    )
)
