"""Test module for the `PayloadStructurePlugin`."""

from shutil import rmtree, copytree
from uuid import uuid4
from copy import deepcopy
import re
from unittest import mock

import pytest
from dcm_common.util import write_test_file, list_directory_content
from dcm_common.logger import LoggingContext as Context

from dcm_ip_builder.plugins import PayloadStructurePlugin


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


@pytest.fixture(scope="session", name="bag_path")
def _bag_path(file_storage):
    return file_storage / "test-bag-structure"


@pytest.fixture(name="duplicate_bag")
def _duplicate_bag(bag_path, testing_config):
    """Duplicates "bag_path" to another directory."""
    duplicate = testing_config.FS_MOUNT_POINT / str(uuid4())
    copytree(bag_path, duplicate)
    return duplicate


@pytest.fixture(name="minimal_profile_url")
def _minimal_profile_url():
    """Provide a minimal payload profile url."""
    return "MINIMAL_PROFILE_URL"


@pytest.fixture(name="minimal_profile")
def _minimal_profile():
    """Provide a minimal payload profile."""
    return {
        "Payload-Folders-Required": ["required_directory"],
        "Payload-Folders-Allowed": [
            "required_directory",
            {
                "regex": r"optional_directory/\d+",
                "example": "optional_directory/4",  # only for this test module
            },
        ],
    }


@pytest.fixture(name="payload_structure_validator")
def _payload_structure_validator(minimal_profile_url, minimal_profile):
    """Provide a minimal payload structure validator."""
    return PayloadStructurePlugin(
        default_profile_url=minimal_profile_url,
        default_profile=minimal_profile
    )


@pytest.fixture(autouse=True)
def run_around_tests(minimal_profile, bag_path):

    # Run before each test starts
    # Generate the example bag in fixtures to (cleaned) working dir.
    if bag_path.is_dir():
        rmtree(bag_path)

    # generate basic test-bag directory structure
    bag_data = bag_path / "data"
    for required in minimal_profile["Payload-Folders-Required"]:
        (bag_data / required).mkdir(parents=True, exist_ok=True)
        write_test_file(bag_data / required / "dummy.txt")

    for allowed in minimal_profile["Payload-Folders-Allowed"]:
        if isinstance(allowed, dict):
            (bag_data / allowed["example"]).mkdir(parents=True, exist_ok=True)
            write_test_file(bag_data / allowed["example"] / "dummy.doc")
        else:
            (bag_data / allowed).mkdir(parents=True, exist_ok=True)

    # Run a test
    yield

    # Run after each test ends
    # Delete folders
    if bag_path.is_dir():
        rmtree(bag_path)


def test_valid_bag(payload_structure_validator, bag_path):
    """Test valid bag."""

    result = payload_structure_validator.get(None, path=str(bag_path))

    assert result.success
    assert result.valid


def test_invalid_bag_required_but_not_allowed_directory(
    minimal_profile, bag_path
):
    """Test bag in which a required directory is not allowed."""

    # modify minimal profile
    modified_profile = deepcopy(minimal_profile)
    modified_profile["Payload-Folders-Required"].append("not_allowed")
    # make additional required directory
    (bag_path / "data" / "not_allowed").mkdir()

    # load modified profile into validator object
    some_validator = PayloadStructurePlugin(
        default_profile_url="modified_profile_url",
        default_profile=modified_profile
    )

    result = some_validator.get(None, path=str(bag_path))

    assert result.success
    assert not result.valid
    pattern_occurs, _ = pattern_in_list_of_strings(
        r".*Required payload directory '.*' not listed in Payload-Folders-Allowed.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )
    assert pattern_occurs


def test_invalid_bag_missing_required_directory(
    payload_structure_validator, minimal_profile, bag_path
):
    """Test bag in which a required directory is missing."""

    RENAME_PATH = (
        bag_path / "data" / minimal_profile["Payload-Folders-Required"][0]
    )

    RENAME_PATH.rename(str(RENAME_PATH) + "_bad")

    result = payload_structure_validator.get(None, path=str(bag_path))

    assert result.success
    assert not result.valid
    pattern_occurs, _ = pattern_in_list_of_strings(
        r".*Required payload directory '.*' is not present.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )
    assert pattern_occurs
    pattern_occurs, _ = pattern_in_list_of_strings(
        r".*File '.*' found in illegal location of payload directory.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )
    assert pattern_occurs


def test_invalid_bag_files_in_every_directory(
    payload_structure_validator, bag_path
):
    """Test bag in which every directory contains a file
    (assuming not all directories are allowed)."""

    # iterate through directory
    dir_list = list_directory_content(
        bag_path,
        pattern="**/*",
        condition_function=lambda p: p.is_dir(),
    )
    for some_dir in dir_list:
        write_test_file(some_dir / "test.dat")

    result = payload_structure_validator.get(None, path=str(bag_path))

    assert result.success
    assert not result.valid
    _, match_count = pattern_in_list_of_strings(
        r".*File '.*' found in illegal location of payload directory.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )

    assert match_count == 2


def test_invalid_bag_files_in_certain_directory(
    payload_structure_validator, bag_path
):
    """Test addition of slash in regex for allowed directories (e.g. if
    Payload-Folders-Allowed reads 'allowed_dir/[0-9]' exclude files
    named 'allowed_dir/4a.dat' and similar)."""

    write_test_file(
        bag_path / "data" / "optional_directory" / "4" / "test.dat",
        mkdir=True,
    )
    write_test_file(
        bag_path / "data" / "optional_directory" / "4atest.dat",
        mkdir=True,
    )
    write_test_file(
        bag_path / "data" / "optional_directory" / "4a" / "test.dat",
        mkdir=True,
    )

    result = payload_structure_validator.get(None, path=str(bag_path))

    assert result.success
    assert not result.valid
    _, match_count = pattern_in_list_of_strings(
        r".*File '.*' found in illegal location of payload directory.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )

    assert match_count == 2


def test_invalid_bag_files_in_certain_directory_noregex(
    payload_structure_validator, bag_path
):
    """Test addition of slash in string (no regex-variant) for allowed
    directories (e.g. if Payload-Folders-Allowed reads 'required_dir'
    exclude files named 'required_dir_a.dat' and similar)."""

    write_test_file(
        bag_path / "data" / "required_directory_test.dat",
        mkdir=True,
    )
    write_test_file(
        bag_path / "data" / "required_directory" / "test.dat",
        mkdir=True,
    )

    result = payload_structure_validator.get(None, path=str(bag_path))

    assert result.success
    assert not result.valid
    pattern_occurs, _ = pattern_in_list_of_strings(
        r".*File '.*' found in illegal location of payload directory.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )
    assert pattern_occurs


def test_invalid_bag_filenames_differ_only_by_capitalization(
    payload_structure_validator, bag_path
):
    """Test bag in which the names of two files differ only in
    capitalization."""

    # write two test files
    write_test_file(
        bag_path / "data" / "required_directory" / "test.dat",
        mkdir=True,
    )
    write_test_file(
        bag_path / "data" / "required_directory" / "TEST.dat",
        mkdir=True,
    )

    result = payload_structure_validator.get(None, path=str(bag_path))

    assert result.success
    assert not result.valid
    pattern_occurs, _ = pattern_in_list_of_strings(
        r".*File '.*' and '.*' only differ in their capitalization.*",
        str(result.log.pick(Context.ERROR)).split("\n"),
    )
    assert pattern_occurs


@pytest.mark.parametrize(
    ("expected_valid", "request_profile"),
    ([
        (True,  False),
        (False, True),
    ])
)
def test_get_request_profile(
    payload_structure_validator,
    bag_path,
    minimal_profile,
    expected_valid,
    request_profile
):
    """
    Test method `get` of `PayloadStructurePlugin` with a profile_url argument.
    """

    # run plugin
    if request_profile:

        # fake get_profile to load another profile
        user_profile = deepcopy(minimal_profile)
        user_profile["Payload-Folders-Required"].append("another_required")
        user_profile["Payload-Folders-Allowed"].append("another_required")
        with mock.patch(
            "dcm_ip_builder.plugins.validation.payload_structure.get_profile",
            side_effect=lambda *args, **kwargs: user_profile,
        ):
            result = payload_structure_validator.get(
                None,
                path=str(bag_path),
                profile_url="user_profile_url",
            )
    else:
        result = payload_structure_validator.get(
            None,
            path=str(bag_path)
        )

    assert result.success
    assert result.valid == expected_valid


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
    payload_structure_validator, duplicate_bag, minimal_profile, keep_file
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
        # add an empty .keep file in an allowed location
        (
            duplicate_bag
            / f"data/{minimal_profile['Payload-Folders-Required'][0]}/.keep"
        ).touch()

    result = payload_structure_validator.get(None, path=str(duplicate_bag))

    assert result.success
    assert result.valid == keep_file  # valid if the .keep file exists
