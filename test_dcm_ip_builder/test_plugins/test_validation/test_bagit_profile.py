"""Test module for the bagit_profile plugin."""

from unittest import mock
from shutil import copytree
from uuid import uuid4
import re
from copy import deepcopy

import pytest
import bagit_utils
from dcm_common.logger import LoggingContext as Context
from dcm_common.util import write_test_file, list_directory_content

from dcm_ip_builder.plugins import BagItProfilePlugin
from dcm_ip_builder.components import Bag, BagItProfileValidator


@pytest.fixture(scope="session", name="bag_path")
def _bag_path(file_storage):
    return file_storage / "test-bag"


@pytest.fixture(name="supported_profiles")
def _supported_profiles(profile_identifier, test_profile):
    return {
        profile_identifier: test_profile
    }


@pytest.fixture(name="duplicate_bag")
def _duplicate_bag(bag_path, testing_config):
    """Duplicates "bag_path" to another directory."""
    duplicate = testing_config.FS_MOUNT_POINT / str(uuid4())
    copytree(bag_path, duplicate)
    return duplicate


def pattern_in_list_of_strings(
    pattern: str, list_of_strings: list[str]
) -> tuple[bool, int]:
    """
    Iterate over a list of strings and count occurrences of pattern.
    """
    occurrences = 0
    for _msg in list_of_strings:
        if re.match(pattern, _msg) is not None:
            occurrences = occurrences + 1
    return occurrences > 0, occurrences


@pytest.mark.parametrize(
    "expected_valid",
    [
        True, False
    ]
)
def test_get(
    supported_profiles,
    bag_path,
    expected_valid
):
    """
    Test method `get` of `BagItProfilePlugin` with faked validator
    function.
    """

    # setup validator
    validator = BagItProfilePlugin(supported_profiles)

    # mock validator to return specific result
    with mock.patch(
        "bagit_utils.BagValidator.validate_once",
        side_effect=lambda *args, **kwargs: bagit_utils.common.ValidationReport(
            expected_valid,
            (
                [bagit_utils.common.Issue("info", "no issues")]
                if expected_valid
                else [bagit_utils.common.Issue("error", "error message")]
            ),
        ),
    ):
        result = validator.get(
            None,
            path=str(bag_path)
        )

    assert result.success
    assert result.valid is expected_valid
    if expected_valid:
        assert Context.ERROR not in result.log
    else:
        assert Context.ERROR in result.log


def test_validate_bag_info(profile_identifier, test_profile, bag_path):
    """
    Test `_validate_bag_info` of `BagItProfilePlugin` regarding LZV.nrw-
    specific description-feature ('description' should behave like
    'regex').
    """

    test_profile["Bag-Info"] = {
        "Property": {
            "description": r"[0-9]*"
        }
    }

    # setup validator
    validator = BagItProfilePlugin(
        {
            profile_identifier: BagItProfileValidator.load_profile(
                profile=test_profile
            )
        }
    )

    # fake bag-object
    class FakeBag(Bag):
        @property
        def baginfo(self):
            return {
                "BagIt-Profile-Identifier": [profile_identifier],
                "Property": ["bad-value", "1"],
            }

    # fake Bag-definition
    with mock.patch(
        "dcm_ip_builder.plugins.validation.bagit_profile.Bag",
        side_effect=FakeBag,
    ):
        # run plugin
        result = validator.get(None, path=str(bag_path))

    assert result.success
    assert len(result.log[Context.ERROR]) == 1
    assert "does not satisfy regex" in result.log[Context.ERROR][0].body
    assert "'bad-value'" in result.log[Context.ERROR][0].body


def test_get_bad_bag(
    test_profile,
    profile_identifier,
    bag_path,
):
    """
    Test method `get` of `BagItProfilePlugin` with a bag not containing
    the required manifests. The bag only contains manifests for sha256
    and sha512.
    """

    test_profile["Manifests-Required"] = ["md5"]

    # setup validator
    validator = BagItProfilePlugin({profile_identifier: test_profile})

    # run plugin
    result = validator.get(None, path=str(bag_path))

    assert result.success
    assert result.valid is False

    assert len(result.log[Context.ERROR]) == 1
    assert (
        "Missing manifest for algorithm 'md5'"
        in result.log[Context.ERROR][0].body
    )


def test_get_no_profile_in_baginfo(
    supported_profiles,
    bag_path,
):
    """
    Test method `get` of `BagItProfilePlugin` without profile in baginfo.
    """

    # setup validator
    validator = BagItProfilePlugin(supported_profiles)

    # fake bag-object
    class FakeBag(Bag):
        @property
        def baginfo(self):
            return super().baginfo | {"BagIt-Profile-Identifier": [None]}

    with mock.patch(
        "dcm_ip_builder.plugins.validation.bagit_profile.Bag",
        side_effect=FakeBag,
    ):
        result = validator.get(
            None,
            path=str(bag_path)
        )

    assert result.success is False


def test_invalid_bag_missing_required_directory(
    duplicate_bag, supported_profiles, test_profile
):
    """Test bag in which a required directory is missing."""

    RENAME_PATH = (
        duplicate_bag / test_profile["Payload-Files-Required"][0]
    )
    RENAME_PATH.rename(str(RENAME_PATH) + "_bad")

    result = BagItProfilePlugin(supported_profiles).get(
        None, path=str(duplicate_bag)
    )

    assert result.success
    assert not result.valid
    assert len(result.log.json["ERROR"]) == 3
    pattern_occurs, _ = pattern_in_list_of_strings(
        r".*Missing required payload-directory*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )
    assert pattern_occurs
    pattern_occurs, _ = pattern_in_list_of_strings(
        r".*Payload file '.*' in Bag at '.*' is not allowed.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )
    assert pattern_occurs


def test_invalid_bag_files_in_certain_directory(
    duplicate_bag, supported_profiles,
):
    """
    Test addition of ** in glob pattern for allowed directories (e.g. if
    Payload-Files-Allowed reads 'allowed_dir/[0-9]', exclude files
    named 'allowed_dir/4a.dat' and similar).
    """

    # allowed files
    write_test_file(
        duplicate_bag / "data" / "optional_directory" / "4" / "test.dat",
        mkdir=True,
    )
    write_test_file(
        duplicate_bag / "data" / "optional_directory" / "45" / "test.dat",
        mkdir=True,
    )
    # not allowed files
    write_test_file(
        duplicate_bag / "data" / "optional_directory" / "4atest.dat",
        mkdir=True,
    )
    write_test_file(
        duplicate_bag / "data" / "optional_directory" / "4a" / "test.dat",
        mkdir=True,
    )
    write_test_file(
        duplicate_bag / "data" / "optional_directory" / "456" / "test.dat",
        mkdir=True,
    )

    result = BagItProfilePlugin(supported_profiles).get(
        None, path=str(duplicate_bag)
    )

    assert result.success
    assert not result.valid
    assert len(result.log.json["ERROR"]) == 3
    _, match_count = pattern_in_list_of_strings(
        r".*Payload file '.*' is not allowed.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )
    assert match_count == 3


def test_invalid_bag_filenames_differ_only_by_capitalization(
    profile_identifier, duplicate_bag,
):
    """
    Test bag in which the names of two files differ only in
    capitalization. Using empty BagIt profile to only test
    the `custom_validation_hook` of the custom `BagValidator`.
    """

    # write two test files
    write_test_file(
        duplicate_bag
        / "data"
        / "test.dat",
        mkdir=True,
    )
    write_test_file(
        duplicate_bag
        / "data"
        / "TEST.dat",
        mkdir=True,
    )
    # write two test files, in directories that differ only by capitalization
    write_test_file(
        duplicate_bag
        / "data"
        / "A"
        / "test.dat",
        mkdir=True,
    )
    write_test_file(
        duplicate_bag
        / "data"
        / "a"
        / "test.dat",
        mkdir=True,
    )

    result = BagItProfilePlugin({profile_identifier: {}}).get(
        None, path=str(duplicate_bag)
    )

    assert result.success
    assert not result.valid
    assert len(result.log.json["ERROR"]) == 2
    pattern_occurs, _ = pattern_in_list_of_strings(
        r".*Files '.*' and '.*' only differ in their capitalization.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )
    assert pattern_occurs


@pytest.mark.parametrize(
    ("keep_file"),
    ([
        (False),
        (True),
    ]),
    ids=[
        "without_keep_file",
        "with_keep_file",
    ]
)
def test_bag_no_payload(
    duplicate_bag, test_profile, supported_profiles, keep_file
):
    """
    Test bag without any payload files.
    Add an empty .keep file to mark as valid.
    """

    # remove payload from bag
    for payload_file in list_directory_content(
        duplicate_bag / "data",
        pattern="**/*",
        condition_function=lambda p: p.is_file()
    ):
        payload_file.unlink()

    if keep_file:
        # add a file at a required location
        write_test_file(
            duplicate_bag
            / test_profile["Payload-Files-Required"][0]
            / ".keep",
            mkdir=True,
        )

    result = BagItProfilePlugin(supported_profiles).get(None, path=str(duplicate_bag))

    assert result.success
    assert result.valid == keep_file  # valid if the .keep file exists


def test_hidden_files(
    duplicate_bag, supported_profiles,
):
    """
    Test bag with hidden files at allowed and not allowed locations.
    """

    # allowed files
    write_test_file(
        duplicate_bag / "data" / "optional_directory" / "4" / ".test",
        mkdir=True,
    )
    write_test_file(
        duplicate_bag / "data" / "optional_directory" / "45" / ".test",
        mkdir=True,
    )
    # not allowed files
    write_test_file(
        duplicate_bag / "data" / "optional_directory" / ".test",
        mkdir=True,
    )

    result = BagItProfilePlugin(supported_profiles).get(
        None, path=str(duplicate_bag)
    )

    assert result.success
    assert not result.valid
    assert len(result.log.json["ERROR"]) == 1
    _, match_count = pattern_in_list_of_strings(
        r".* Payload file 'data/optional_directory/.test' in Bag at '.*' is not allowed.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )
    assert match_count == 1


@pytest.mark.parametrize(
    ("supported_profiles", "load_bagit_profile_from_bag", "success"),
    ([
        ({}, False, True),
        (None, False, False),
        (None, True, True),
    ])
)
def test_constructor(supported_profiles, load_bagit_profile_from_bag, success):
    """Test constructor of the `BagItProfilePlugin`."""

    if success:
        BagItProfilePlugin(supported_profiles, load_bagit_profile_from_bag)
    else:
        with pytest.raises(ValueError):
            BagItProfilePlugin(supported_profiles, load_bagit_profile_from_bag)


@pytest.mark.parametrize(
    (
        "profile_in_store",
        "profile_online",
        "profile_accepts_serialization",
        "profile_no_support_version_1",
        "success",
    ),
    [
        (True, True, False, False, True),
        (True, False, False, False, True),
        (False, True, False, False, True),
        (False, True, True, False, False),  # profile accepts serialized bags
        (False, True, False, True, False),  # profile does not support BagIt-Version 1.0
        (False, False, False, False, False),
    ],
)
def test_load_bagit_profile_from_bag(
    duplicate_bag,
    profile_identifier,
    test_profile,
    profile_in_store,
    profile_online,
    profile_accepts_serialization,
    profile_no_support_version_1,
    success,
):
    """
    Test method `get` of `BagItProfilePlugin` when loading the bagit profile
    from the bag.
    """

    this_test_profile = deepcopy(test_profile)

    if profile_accepts_serialization:
        this_test_profile["Accept-Serialization"] = ["application/zip"]
    if profile_no_support_version_1:
        this_test_profile["Accept-BagIt-Version"] = ["0.97"]

    if profile_in_store:
        validator = BagItProfilePlugin(
            supported_profiles={profile_identifier: this_test_profile},
            load_bagit_profile_from_bag=True,
        )
    else:
        validator = BagItProfilePlugin(
            load_bagit_profile_from_bag=True
        )

    if profile_online:
        # fake profile-url server
        with mock.patch(
            "bagit_utils.validator.load_json_url",
            side_effect=lambda *args, **kwargs: this_test_profile,
        ):

            result = validator.get(None, path=str(duplicate_bag))

    else:
        result = validator.get(None, path=str(duplicate_bag))

    if success:
        assert result.success
        assert result.valid
    else:
        assert result.success is False
        assert Context.ERROR in result.log
        assert len(result.log.json["ERROR"]) == 1
        assert "Unable to load profile" in result.log.json["ERROR"][0]["body"]
        assert result.valid is None
