from pathlib import Path
from json import dumps

import pytest
from bagit_utils import Bag
from dcm_common.services.tests import (
    fs_setup, fs_cleanup, external_service, run_service, wait_for_report
)

import dcm_ip_builder
from dcm_ip_builder.config import AppConfig
from dcm_ip_builder.plugins.mapping import DemoMappingPlugin
from dcm_ip_builder.components import BagItProfileValidator


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
def _testing_config(file_storage, test_profile):
    """Returns test-config"""
    # setup config-class
    static_profile = BagItProfileValidator.load_profile(
        profile_src=(
            Path(dcm_ip_builder.__file__).parent / "static/bagit_profile.json"
        )
    )

    class TestingConfig(AppConfig):
        FS_MOUNT_POINT = file_storage
        TESTING = True
        ORCHESTRA_DAEMON_INTERVAL = 0.01
        ORCHESTRA_WORKER_INTERVAL = 0.01
        ORCHESTRA_WORKER_ARGS = {"messages_interval": 0.01}
        PROFILES_SRC = (
            "["
            + f"{dumps(test_profile)}, "
            + f"{dumps(static_profile)}]"
        )

        MAPPING_PLUGINS = [DemoMappingPlugin]
    return TestingConfig


@pytest.fixture(name="test_bag_baginfo")
def _test_bag_baginfo(fixtures):
    return Bag(fixtures / "test-bag").baginfo


@pytest.fixture(name="profile_identifier")
def _profile_identifier():
    return "https://lzv.nrw/bagit_profile.json"


@pytest.fixture(name="test_profile")
def _test_profile(profile_identifier):
    return {
            "BagIt-Profile-Info": {
                "Source-Organization": "",
                "External-Description": "",
                "Version": "",
                "BagIt-Profile-Identifier": profile_identifier,
            },
            "Bag-Info": {},
            "Manifests-Required": [],
            "Accept-BagIt-Version": ["1.0"],
            "Payload-Files-Required": ["data/preservation_master/"],
            "Payload-Files-Allowed": [
                "data/preservation_master/*",
                "data/optional_directory/[0-9]/*",
                "data/optional_directory/[0-9][0-9]/*",
            ],
        }
