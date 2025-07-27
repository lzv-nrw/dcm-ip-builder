"""Test module for the bagit_profile plugin."""

from unittest import mock

import pytest
import bagit_utils
from dcm_common.logger import LoggingContext as Context

from dcm_ip_builder.plugins import BagItProfilePlugin


@pytest.fixture(scope="session", name="bag_path")
def _bag_path(file_storage):
    return file_storage / "test-bag"


@pytest.fixture(name="profile_identifier")
def _profile_identifier(testing_config):
    return testing_config.BAGIT_PROFILE_URL


@pytest.fixture(name="bagit_profile_info")
def _baginfo_profile_info(profile_identifier):
    return {
        "Source-Organization": "",
        "External-Description": "",
        "Version": "",
        "BagIt-Profile-Identifier": profile_identifier,
    }


@pytest.fixture(name="bagit_profile_dict")
def _baginfo_profile_dict(bagit_profile_info):
    return {
        "BagIt-Profile-Info": bagit_profile_info,
        "Bag-Info": {
        },
        "Manifests-Required": [
        ],
        "Accept-BagIt-Version": [
            "1.0"
        ]
    }


def test_bagit_profile(bagit_profile_dict):
    """
    Test proper instantiation of `BagItProfilePlugin`
    """

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url="url",
        default_profile=bagit_profile_dict
    )
    assert validator.default_bagit_profile


@pytest.mark.parametrize(
    "expected_valid",
    [
        True, False
    ]
)
def test_get(
    profile_identifier,
    bagit_profile_dict,
    bag_path,
    expected_valid
):
    """
    Test method `get` of `BagItProfilePlugin` with faked validator
    function.
    """

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict,
    )

    # mock profile-url server + validator to return specific result
    with mock.patch(
        "bagit_utils.validator.load_json_url",
        side_effect=lambda *args, **kwargs: bagit_profile_dict,
    ), mock.patch(
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


def test_validate_bag_info(profile_identifier, bagit_profile_dict, bag_path):
    """
    Test `_validate_bag_info` of `BagItProfilePlugin` regarding LZV.nrw-
    specific description-feature (fake other components like
    `bagit_profile.Profile.validate`, `bagit_profile.Profile.validate_bag_info`
    and `pathlib.Path.is_file`).
    """

    bagit_profile_dict["Bag-Info"] = {
        "Property": {
            "description": r"[0-9]*"
        }
    }

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict,
    )

    # fake bag-object
    class FakeBag(bagit_utils.Bag):
        @property
        def baginfo(self):
            return {"Property": ["bad-value", "1"]}

    # fake profile-url server + Bag-definition
    with mock.patch(
        "bagit_utils.validator.load_json_url",
        side_effect=lambda *args, **kwargs: bagit_profile_dict,
    ), mock.patch("bagit_utils.Bag", side_effect=FakeBag):
        # run plugin
        result = validator.get(None, path=str(bag_path))

    assert len(result.log[Context.ERROR]) == 1
    assert "does not satisfy regex" in result.log[Context.ERROR][0].body
    assert "'bad-value'" in result.log[Context.ERROR][0].body


def test_get_bad_bag(
    profile_identifier,
    bagit_profile_dict,
    bag_path
):
    """
    Test method `get` of `BagItProfilePlugin` with a bag not containing
    the required manifests. The bag only contains manifests for sha256
    and sha512.
    """

    bagit_profile_dict["Manifests-Required"] = ["md5"]

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict
    )

    # fake profile-url server
    with mock.patch(
        "bagit_utils.validator.load_json_url",
        side_effect=lambda *args, **kwargs: bagit_profile_dict,
    ):
        # run plugin
        result = validator.get(
            None,
            path=str(bag_path)
        )

    assert result.success
    assert result.valid is False

    assert len(result.log[Context.ERROR]) == 1
    assert (
        "Missing manifest for algorithm 'md5'"
        in result.log[Context.ERROR][0].body
    )


def test_get_default_profile(
    profile_identifier,
    bagit_profile_dict,
    bag_path,
):
    """
    Test method `get` of `BagItProfilePlugin` without profile in request
    or bag.
    """

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict,
    )

    # fake bag-object
    class FakeBag(bagit_utils.Bag):
        @property
        def baginfo(self):
            return super().baginfo | {"BagIt-Profile-Identifier": [None]}

    with mock.patch("bagit_utils.Bag", side_effect=FakeBag):
        result = validator.get(
            None,
            path=str(bag_path)
        )

    assert result.success


def test_get_profile_error(
    profile_identifier,
    bagit_profile_dict,
    bag_path,
):
    """
    Test method `get` of `BagItProfilePlugin` for an error
    while loading the profile.
    """

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict
    )

    # run plugin
    result = validator.get(
        None,
        path=str(bag_path),
    )

    assert result.success is True
    assert Context.ERROR in result.log
    assert len(result.log[Context.ERROR]) == 1
    assert "Unable to load profile" in result.log[Context.ERROR][0].body
