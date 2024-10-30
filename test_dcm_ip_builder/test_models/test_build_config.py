"""BuildConfig-data model test-module."""

from pathlib import Path

import pytest
from dcm_common.models.data_model import get_model_serialization_test

from dcm_ip_builder.models.build_config import _BuildConfig
from dcm_ip_builder.models import BuildConfig, Target


@pytest.fixture(name="config")
def _config():
    class Config:
        CONVERTER = "converter"
        MAPPER = "mapper"
    return Config


def test_BuildConfig_json(config):
    """Test property `json` of model `BuildConfig`."""

    json = BuildConfig(
        Target(Path(".")),
        config,
        "bagit_profile_url",
        "payload_profile_url"
    ).json

    assert "target" in json
    assert "bagit_profile_url" in json
    assert "payload_profile_url" in json


def test_BuildConfig_additional_properties(config):
    """
    Test properties `converter` and `converter` of model `BuildConfig`.
    """

    build_config = BuildConfig(
        Target(Path(".")),
        config
    )

    assert build_config.converter == config.CONVERTER
    assert build_config.mapper == config.MAPPER


test_handler_build_config_json = get_model_serialization_test(
    _BuildConfig, (
        (
            (
                Target(Path(".")),
                "config"
            ),
            {}
        ),
    )
)
