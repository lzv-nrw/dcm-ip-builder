"""
Test module for the `dcm_ip_builder/handlers.py`.
"""

import base64

import pytest
from data_plumber_http.settings import Responses
from dcm_s11n.vinegar import Vinegar

from dcm_ip_builder import handlers


@pytest.fixture(name="validate_ip_handler")
def _validate_ip_handler(fixtures):
    return handlers.get_validate_ip_handler(
        fixtures,
        ["some-module"],
        "some_profile",
        "some_profile"
    )


@pytest.mark.parametrize(
    ("json", "status"),
    (pytest_args := [
        (
            {"no-validation": None},
            400
        ),
        (  # missing target
            {"validation": {}},
            400
        ),
        (  # missing path
            {"validation": {"target": {}}},
            400
        ),
        (
            {"validation": {"target": {"path": "test-bag_"}}},
            404
        ),
        (
            {"validation": {"target": {"path": "test-bag"}}},
            Responses.GOOD.status
        ),
    ]),
    ids=[f"stage {i+1}" for i in range(len(pytest_args))]
)
def test_validate_ip_handler(
    validate_ip_handler, json, status, fixtures
):
    "Test `validate_ip_handler`."

    output = validate_ip_handler.run(json=json)

    assert output.last_status == status
    if status != Responses.GOOD.status:
        print(output.last_message)
    else:
        assert fixtures not in output.data.value["validation"]["target"].path.parents


@pytest.fixture(name="build_handler")
def _build_handler(fixtures):
    return handlers.get_build_handler(
        fixtures,
        ["some-module"],
        "some_profile",
        "some_profile"
    )


@pytest.fixture(name="serialized_build_config")
def _serialized_build_config():
    class Converter:
        def get_dict(self):
            pass
    class Mapper:
        def get_metadata(self):
            pass
    class _Config:
        CONVERTER = Converter
        MAPPER = Mapper
    return base64.b64encode(
        Vinegar(None).dumps(_Config)
    ).decode(encoding="utf-8")


@pytest.mark.parametrize(
    ("json", "status"),
    (pytest_args := [
        (
            {"no-build": None},
            400
        ),
        (  # missing target
            {"build": {"configuration": "good"}},
            400
        ),
        (  # missing path
            {"build": {"target": {}, "configuration": "good"}},
            400
        ),
        (  # missing configuration
            {"build": {"target": {"path": "test-bag"}}},
            400
        ),
        (  # target does not exist
            {"build": {"target": {"path": "test-bag_"}, "configuration": "good"}},
            404
        ),
        (
            {"build": {"target": {"path": "test-bag"}, "configuration": "good"}},
            Responses.GOOD.status
        ),
        (
            {
                "build": {"target": {"path": "test-bag"}, "configuration": "good"},
                "validation": None
            },
            422
        ),
        (
            {
                "build": {"target": {"path": "test-bag"}, "configuration": "good"},
                "validation": {"modules": None}
            },
            422
        ),
        (
            {
                "build": {"target": {"path": "test-bag"}, "configuration": "good"},
                "validation": {"args": None}
            },
            422
        ),
        (
            {
                "build": {"target": {"path": "test-bag"}, "configuration": "good"},
                "validation": {"modules": [], "args": {}}
            },
            Responses.GOOD.status
        ),
    ]),
    ids=[f"stage {i+1}" for i in range(len(pytest_args))]
)
def test_build_handler(
    build_handler, serialized_build_config, json, status, fixtures
):
    "Test `build_handler`."

    try:
        if json["build"]["configuration"] == "good":
            json["build"]["configuration"] = serialized_build_config
    except KeyError:
        pass

    output = build_handler.run(json=json)

    assert output.last_status == status
    if status != Responses.GOOD.status:
        print(output.last_message)
    else:
        assert fixtures not in output.data.value["build"].target.path.parents


@pytest.mark.parametrize(
    ("preset", "status"),
    (pytest_args := [
        ("nonsense", 400),
        ("bad_base64", 400),
        ("okay", Responses.GOOD.status),
        ("missing_CONVERTER_missing_MAPPER", 422),
        ("missing_CONVERTER", 422),
        ("missing_MAPPER", 422),
        ("missing_CONVERTER.get_dict", 422),
        ("missing_MAPPER.get_metadata", 422),
    ]),
    ids=[x[0] for x in pytest_args]
)
def test_BUILD_CONFIGURATION_HANDLER(build_handler, preset, status):
    """Test BUILD_CONFIGURATION_HANDLER."""

    class Converter:
        def get_dict(self):
            pass
    class Mapper:
        def get_metadata(self):
            pass

    match preset:
        case "nonsense":
            Config = "string"
        case "bad_base64":
            class _Config:
                CONVERTER = Converter
                MAPPER = Mapper
            Config = _Config
        case "okay":
            class _Config:
                CONVERTER = Converter
                MAPPER = Mapper
            Config = _Config
        case "missing_CONVERTER_missing_MAPPER":
            class _Config:
                pass
            Config = _Config
        case "missing_CONVERTER":
            class _Config:
                MAPPER = Mapper
            Config = _Config
        case "missing_MAPPER":
            class _Config:
                CONVERTER = Converter
            Config = _Config
        case "missing_CONVERTER.get_dict":
            class _Config:
                CONVERTER = str
                MAPPER = Mapper
            Config = _Config
        case "missing_MAPPER.get_metadata":
            class _Config:
                CONVERTER = Converter
                MAPPER = str
            Config = _Config

    json = {
        "build": {
            "target": {"path": "test-bag"},
            "configuration": base64.b64encode(
                Vinegar(None).dumps(Config)
            ).decode(encoding="utf-8")}
    }
    if preset == "nonsense":
        json["build"]["configuration"] = "nonsense"
    if preset == "bad_base64":
        json["build"]["configuration"] = \
            json["build"]["configuration"][:4] + "_" + json["build"]["configuration"][5:]

    output = build_handler.run(
        json=json
    )
    assert output.last_status == status
    if status != Responses.GOOD.status:
        print(output.last_message)
