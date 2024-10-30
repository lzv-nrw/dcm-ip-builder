"""
Test module for the package `dcm-ip-builder-sdk`.
"""

from time import sleep

import pytest
import dcm_ip_builder_sdk

from dcm_ip_builder import app_factory


@pytest.fixture(name="app")
def _app(testing_config):
    testing_config.ORCHESTRATION_AT_STARTUP = True
    return app_factory(testing_config(), as_process=True)


@pytest.fixture(name="default_sdk", scope="module")
def _default_sdk():
    return dcm_ip_builder_sdk.DefaultApi(
        dcm_ip_builder_sdk.ApiClient(
            dcm_ip_builder_sdk.Configuration(
                host="http://localhost:8080"
            )
        )
    )


@pytest.fixture(name="build_sdk", scope="module")
def _build_sdk():
    return dcm_ip_builder_sdk.BuildApi(
        dcm_ip_builder_sdk.ApiClient(
            dcm_ip_builder_sdk.Configuration(
                host="http://localhost:8080"
            )
        )
    )


@pytest.fixture(name="validation_sdk", scope="module")
def _validation_sdk():
    return dcm_ip_builder_sdk.ValidationApi(
        dcm_ip_builder_sdk.ApiClient(
            dcm_ip_builder_sdk.Configuration(
                host="http://localhost:8080"
            )
        )
    )


def test_default_ping(
    default_sdk: dcm_ip_builder_sdk.DefaultApi, app, run_service
):
    """Test default endpoint `/ping-GET`."""

    run_service(app)

    response = default_sdk.ping()

    assert response == "pong"


def test_default_status(
    default_sdk: dcm_ip_builder_sdk.DefaultApi, app, run_service
):
    """Test default endpoint `/status-GET`."""

    run_service(app)

    response = default_sdk.get_status()

    assert response.ready


def test_default_identify(
    default_sdk: dcm_ip_builder_sdk.DefaultApi, app, run_service,
    testing_config
):
    """Test default endpoint `/identify-GET`."""

    run_service(app)

    response = default_sdk.identify()

    assert response.to_dict() == testing_config().CONTAINER_SELF_DESCRIPTION


def test_build_report(
    build_sdk: dcm_ip_builder_sdk.BuildApi, app, run_service,
    testing_config, minimal_build_config
):
    """Test endpoints `/build-POST` and `/report-GET`."""

    run_service(app)

    submission = build_sdk.build(
        {
            "build": {
                "target": {
                    "path": str("test-ie")
                },
                "configuration": minimal_build_config
            },
            "validation": {"modules": []}
        }
    )

    while True:
        try:
            report = build_sdk.get_report(token=submission.value)
            break
        except dcm_ip_builder_sdk.exceptions.ApiException as e:
            assert e.status == 503
            sleep(2)

    assert report.data.actual_instance.valid
    assert (
        testing_config().FS_MOUNT_POINT / report.data.actual_instance.path
    ).is_dir()


def test_validation_report(
    validation_sdk: dcm_ip_builder_sdk.ValidationApi, app, run_service
):
    """Test endpoints `/validate/ip-POST` and `/report-GET`."""

    run_service(app)

    submission = validation_sdk.validate_ip(
        {
            "validation": {
                "target": {
                    "path": str("test-bag")
                },
                "modules": ["bagit_profile"]
            }
        }
    )

    while True:
        try:
            report = validation_sdk.get_report(token=submission.value)
            break
        except dcm_ip_builder_sdk.exceptions.ApiException as e:
            assert e.status == 503
            sleep(2)

    assert report.data.actual_instance.valid


def test_build_report_404(
    build_sdk: dcm_ip_builder_sdk.BuildApi, app, run_service
):
    """Test build endpoint `/report-GET` without previous submission."""

    run_service(app)

    with pytest.raises(dcm_ip_builder_sdk.rest.ApiException) as exc_info:
        build_sdk.get_report(token="some-token")
    assert exc_info.value.status == 404
