from pathlib import Path

import pytest
from bagit_utils import Bag
from dcm_common.services.tests import (
    fs_setup, fs_cleanup, external_service, run_service, wait_for_report
)

from dcm_ip_builder.config import AppConfig
from dcm_ip_builder.plugins.mapping import DemoMappingPlugin


# define fixture-directory
@pytest.fixture(scope="session", name="fixtures")
def _fixtures():
    return Path("test_dcm_ip_builder/fixtures")


@pytest.fixture(scope="session", name="file_storage")
def _file_storage():
    return Path("test_dcm_ip_builder/file_storage")


@pytest.fixture(scope="session", autouse=True)
def disable_extension_logging():
    """
    Disables the stderr-logging via the helper method `print_status`
    of the `dcm_common.services.extensions`-subpackage.
    """
    # pylint: disable=import-outside-toplevel
    from dcm_common.services.extensions.common import PrintStatusSettings

    PrintStatusSettings.silent = True


@pytest.fixture(name="testing_config")
def _testing_config(file_storage):
    """Returns test-config"""
    # setup config-class
    class TestingConfig(AppConfig):
        FS_MOUNT_POINT = file_storage
        TESTING = True
        ORCHESTRA_DAEMON_INTERVAL = 0.01
        ORCHESTRA_WORKER_INTERVAL = 0.01
        ORCHESTRA_WORKER_ARGS = {"messages_interval": 0.01}

        MAPPING_PLUGINS = [DemoMappingPlugin]
        BAGIT_PROFILE_URL = "https://lzv.nrw/test_bagit_profile.json"
        BAGIT_PROFILE = {
            "BagIt-Profile-Info": {
                "Source-Organization": "Some source organization",
                "External-Description": "Some description",
                "BagIt-Profile-Identifier": "https://lzv.nrw/test_bagit_profile.json",
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
        PAYLOAD_PROFILE_URL = "https://lzv.nrw/test_payload_profile.json"
        PAYLOAD_PROFILE = {
            "BagIt-Payload-Profile-Info": {
                "Version": "0.3.2"
            }
        }
    return TestingConfig


@pytest.fixture(name="test_bag_baginfo")
def _test_bag_baginfo(fixtures):
    return Bag(fixtures / "test-bag").baginfo
