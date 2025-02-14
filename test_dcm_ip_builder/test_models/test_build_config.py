"""BuildConfig-data model test-module."""

from pathlib import Path

from dcm_common.models.data_model import get_model_serialization_test
from dcm_common.services.plugins import PluginConfig

from dcm_ip_builder.models import BuildConfig, Target


test_BuildConfig_json = get_model_serialization_test(
    BuildConfig,
    (
        ((Target(Path(".")), PluginConfig("plugin-name", {})), {}),
        (
            (
                Target(Path(".")),
                PluginConfig("plugin-name", {}),
                "bagit-url",
                "payload-url",
            ),
            {},
        ),
    ),
)
