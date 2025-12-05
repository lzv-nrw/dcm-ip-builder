"""
Test module for the app config.
"""

from json import dumps

import pytest
from dcm_common.util import write_test_file

from dcm_ip_builder.config import AppConfig


@pytest.mark.parametrize(
    ("success", "default_profile"),
    (
        [
            (
                True,
                "unknown-profile",
            ),  # warning printed; profile not supported for validation
            (True, "https://lzv.nrw/test_profile.json"),
        ]
    ),
)
def test_profile_sources_default_profile(
    file_storage, success, default_profile
):
    """
    Test behavior of `AppConfig`-constructor for profile sources
    and default profile for build.
    """
    class TestConfig(AppConfig):
        FS_MOUNT_POINT = file_storage
        DEFAULT_BAGIT_PROFILE = default_profile

    if success:
        TestConfig()
    else:
        with pytest.raises(ValueError):
            TestConfig()


@pytest.mark.parametrize(
    ("success", "profile_sources", "profile_uris"),
    (
        [
            (
                True,
                None,
                ["https://github.com/lzv-nrw/spec-information-package/raw/refs/tags/0.7.0/profiles/lzvnrw_bagit_profile.json"],
            ),  # loads profiles from 'static' directory
            (True, "[]", []),  # OK (list of supported profiles is empty)
            (True, '["test"]', []),  # invalid profile -> empty list
            (
                True,
                '[{"field": "value"}]',
                [],
            ),  # invalid profile (missing 'BagIt-Profile-Info')
            (
                True,
                '[{"BagIt-Profile-Info": "value"}]',
                [],
            ),  # invalid profile (missing 'BagIt-Profile-Identifier' field)
            (
                False,
                (
                    '['
                    + '{"BagIt-Profile-Info": {"BagIt-Profile-Identifier": "uri1"}}, '
                    + '{"BagIt-Profile-Info": {"BagIt-Profile-Identifier": "uri1"}}'
                    + ']'
                ),
                None,
            ),  # error (non-unique uri)
            (
                True,
                (
                    '['
                    + '{"BagIt-Profile-Info": {"BagIt-Profile-Identifier": "uri1"}}, '
                    + '{"BagIt-Profile-Info": {"BagIt-Profile-Identifier": "uri2"}}'
                    + ']'
                ),
                ["uri1", "uri2"],
            ),  # OK (unique uris)
            (
                True,
                (
                    '['
                    + '{"BagIt-Profile-Info": {"BagIt-Profile-Identifier": "uri1"}, "Serialization": "forbidden", "Accept-Serialization": [], "Accept-BagIt-Version": ["1.0"]}'
                    + ']'
                ),
                ["uri1"],
            ),  # OK (allowed values for 'Serialization', 'Accept-Serialization' and 'Accept-BagIt-Version')
            (
                True,
                (
                    '['
                    + '{"BagIt-Profile-Info": {"BagIt-Profile-Identifier": "uri1"}, "Serialization": "optional"}'
                    + ']'
                ),
                [],
            ),  # invalid profile (not allowed value for 'Accept-Serialization')
            (
                True,
                (
                    '['
                    + '{"BagIt-Profile-Info": {"BagIt-Profile-Identifier": "uri1"}, "Accept-Serialization": ["application/zip"]}'
                    + ']'
                ),
                [],
            ),  # invalid profile (not allowed value for 'Accept-Serialization')
            (
                True,
                (
                    '['
                    + '{"BagIt-Profile-Info": {"BagIt-Profile-Identifier": "uri1"}, "Accept-BagIt-Version": ["0.97"]}'
                    + ']'
                ),
                [],
            ),  # invalid profile (not allowed value for 'Accept-BagIt-Version')
        ]
    ),
)
def test_profile_sources(file_storage, success, profile_sources, profile_uris):
    """
    Test behavior of `AppConfig`-constructor for profile sources.
    """

    if profile_sources is not None:
        class TestConfig(AppConfig):
            FS_MOUNT_POINT = file_storage
            PROFILES_SRC = profile_sources
    else:
        class TestConfig(AppConfig):
            FS_MOUNT_POINT = file_storage

    if success:
        test_config = TestConfig()
        assert sorted(list(test_config.supported_profiles.keys())) == sorted(
            profile_uris
        )
    else:
        with pytest.raises(ValueError):
            TestConfig()


@pytest.mark.parametrize(
    ("invalid_profile_in_dir"),
    (
        [
            (False,),
            (True,),
        ]
    ),
)
def test_profile_sources_from_dir(
    file_storage,
    invalid_profile_in_dir,
):
    """
    Test behavior of `AppConfig`-constructor for profile sources from
    a directory.
    """

    # setup directory for profiles
    (file_storage / "profiles").mkdir(exist_ok=True)
    # write minimal valid profile
    (file_storage / "profiles" / "test_profile.json").write_text(
        dumps(
            {"BagIt-Profile-Info": {"BagIt-Profile-Identifier": "profile-uri"}}
        ),
        encoding="utf-8",
    )

    if invalid_profile_in_dir:
        write_test_file(
            file_storage / "profiles" / "test.dat",
            mkdir=True,
        )

    class TestConfig(AppConfig):
        FS_MOUNT_POINT = file_storage
        PROFILES_SRC = "profiles"  # load profiles from 'profiles' directory

    test_config = TestConfig()
    assert sorted(list(test_config.supported_profiles.keys())) == sorted(
        ["profile-uri"]
    )
