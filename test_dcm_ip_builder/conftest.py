from pathlib import Path

import pytest
from dcm_common.services.tests import (
    fs_setup, fs_cleanup, external_service, run_service, wait_for_report
)

from dcm_ip_builder import app_factory
from dcm_ip_builder.config import AppConfig


# define fixture-directory
@pytest.fixture(scope="session", name="fixtures")
def _fixtures():
    return Path("test_dcm_ip_builder/fixtures")


@pytest.fixture(scope="session", name="file_storage")
def _file_storage():
    return Path("test_dcm_ip_builder/file_storage")


@pytest.fixture(name="minimal_build_config")
def _minimal_build_config(fixtures):
    return "file://" + str((fixtures / "test-config.py").absolute())


@pytest.fixture(name="testing_config")
def _testing_config(file_storage):
    """Returns test-config"""
    # setup config-class
    class TestingConfig(AppConfig):
        ORCHESTRATION_AT_STARTUP = False
        ORCHESTRATION_DAEMON_INTERVAL = 0.001
        ORCHESTRATION_ORCHESTRATOR_INTERVAL = 0.001
        ORCHESTRATION_ABORT_NOTIFICATIONS_STARTUP_INTERVAL = 0.01
        TESTING = True
        USE_OBJECT_VALIDATOR = False
        FS_MOUNT_POINT = file_storage

        BAGIT_PROFILE_URL = "https://lzv.nrw/bagit_profile.json"
        BAGIT_PROFILE = {
            "BagIt-Profile-Info": {
                "Source-Organization": "Some source organization",
                "External-Description": "Some description",
                "BagIt-Profile-Identifier": "https://lzv.nrw/bagit_profile.json",
                "Version": "0.3.2"
            },
            "Bag-Info": {
                "DC-Title": {
                    "required": True,
                    "repeatable": False
                },
                "BagIt-Profile-Identifier": {
                    "required": True,
                    "repeatable": False,
                    "description": "(https|http|sftp|file):\\/\\/\\S*"
                },
                "BagIt-Payload-Profile-Identifier": {
                    "required": True,
                    "repeatable": False,
                    "description": "(https|http|sftp|file):\\/\\/\\S*"
                },
                "Bag-Software-Agent": {
                    "required": False,
                    "repeatable": False,
                    "description": ".* v[\\w\\.\\-\\+]+"
                },
                "Bagging-DateTime": {
                    "required": True,
                    "repeatable": False,
                    "description": "(\\d{4}-[01]\\d-[0-3]\\dT[0-2]\\d:[0-5]\\d:[0-5]\\d\\.\\d+([+-][0-2]\\d:[0-5]\\d|Z))|(\\d{4}-[01]\\d-[0-3]\\dT[0-2]\\d:[0-5]\\d:[0-5]\\d([+-][0-2]\\d:[0-5]\\d|Z))|(\\d{4}-[01]\\d-[0-3]\\dT[0-2]\\d:[0-5]\\d([+-][0-2]\\d:[0-5]\\d|Z))"
                },
            },
            "Manifests-Required": [],
            "Manifests-Allowed": ["sha512", "sha256"],
            "Tag-Manifests-Required": [],
            "Tag-Manifests-Allowed": ["sha512", "sha256"],
            "Accept-BagIt-Version": ["1.0"]
        }
        # payload profile
        PAYLOAD_PROFILE_URL = "https://lzv.nrw/payload_profile.json"
        PAYLOAD_PROFILE = {
            "BagIt-Payload-Profile-Info": {
                "Version": "0.3.2"
            }
        }
        DEFAULT_VALIDATOR_KWARGS = {
            "bagit_profile": {
                "bagit_profile_url": BAGIT_PROFILE_URL,
                "bagit_profile": BAGIT_PROFILE,
            }
        }
    return TestingConfig


@pytest.fixture(name="client")
def _client(testing_config):
    """
    Returns test_client.
    """

    return app_factory(testing_config()).test_client()
