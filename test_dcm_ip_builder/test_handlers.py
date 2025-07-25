"""
Test module for the `dcm_ip_builder/handlers.py`.
"""


import pytest
from data_plumber_http.settings import Responses

from dcm_ip_builder import handlers
from dcm_ip_builder.plugins.mapping import DemoMappingPlugin


@pytest.fixture(name="validate_ip_handler")
def _validate_ip_handler(fixtures):
    return handlers.get_validate_ip_handler(fixtures)


@pytest.mark.parametrize(
    ("json", "status"),
    (
        pytest_args := [
            ({"no-validation": None}, 400),
            ({"validation": {}}, 400),  # missing target
            ({"validation": {"target": {}}}, 400),  # missing path
            (  # path is no dir
                {"validation": {"target": {"path": "test-bag_"}}},
                404,
            ),
            (  # no profiles
                {"validation": {"target": {"path": "test-bag"}}},
                Responses.GOOD.status,
            ),
            (  # BagItProfile arg
                {
                    "validation": {
                        "target": {"path": "test-bag"},
                        "BagItProfile": "request_bagit_profile",
                    }
                },
                Responses.GOOD.status,
            ),
            (  # BagItPayloadProfile arg
                {
                    "validation": {
                        "target": {"path": "test-bag"},
                        "BagItPayloadProfile": "request_payload_profile",
                    }
                },
                Responses.GOOD.status,
            ),
            (  # with both profile args
                {
                    "validation": {
                        "target": {"path": "test-bag"},
                        "BagItProfile": "request_bagit_profile",
                        "BagItPayloadProfile": "request_payload_profile",
                    }
                },
                Responses.GOOD.status,
            ),
        ]
    ),
    ids=[f"stage {i+1}" for i in range(len(pytest_args))],
)
def test_validate_ip_handler(
    validate_ip_handler, json, status
):
    "Test `validate_ip_handler`."

    output = validate_ip_handler.run(json=json)

    assert output.last_status == status
    if status != Responses.GOOD.status:
        print(output.last_message)


@pytest.fixture(name="build_handler")
def _build_handler(fixtures):
    return handlers.get_build_handler(
        {DemoMappingPlugin.name: DemoMappingPlugin()},
        fixtures
    )


@pytest.mark.parametrize(
    ("json", "status"),
    (pytest_args := [
        (
            {"no-build": None},
            400
        ),
        (  # missing target
            {"build": {"mappingPlugin": {"plugin": "demo", "args": {}}}},
            400
        ),
        (  # missing path
            {"build": {"target": {}, "mappingPlugin": {"plugin": "demo", "args": {}}}},
            400
        ),
        (  # missing mapping
            {"build": {"target": {"path": "test-bag"}}},
            400
        ),
        (  # unknown mapping
            {"build": {"target": {"path": "test-bag"}, "mappingPlugin": {"plugin": "unknown", "args": {}}}},
            422
        ),
        (  # bad mapping
            {"build": {"target": {"path": "test-bag"}, "mappingPlugin": None}},
            422
        ),
        (  # target does not exist
            {"build": {"target": {"path": "test-bag_"}, "mappingPlugin": {"plugin": "demo", "args": {}}}},
            404
        ),
        (
            {"build": {"target": {"path": "test-bag"}, "mappingPlugin": {"plugin": "demo", "args": {}}}},
            Responses.GOOD.status
        ),
        (  # validate
            {"build": {"target": {"path": "test-bag"}, "mappingPlugin": {"plugin": "demo", "args": {}}, "validate": False}},
            Responses.GOOD.status
        ),
    ]),
    ids=[f"stage {i+1}" for i in range(len(pytest_args))]
)
def test_build_handler(
    build_handler, json, status
):
    "Test `build_handler`."

    output = build_handler.run(json=json)

    assert output.last_status == status
    if status != Responses.GOOD.status:
        print(output.last_message)
