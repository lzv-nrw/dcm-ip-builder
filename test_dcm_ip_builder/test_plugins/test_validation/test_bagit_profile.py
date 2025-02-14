"""Test module for the bagit_profile plugin."""

from copy import deepcopy
from unittest import mock

import pytest
from bagit_profile import ProfileValidationReport, ProfileValidationError
from dcm_common.logger import LoggingContext as Context

from dcm_ip_builder.plugins import BagItProfilePlugin


@pytest.fixture(scope="session", name="bag_path")
def _bag_path(file_storage):
    return file_storage / "test-bag"


@pytest.fixture(scope="session", name="bad_bag_path")
def _bad_bag_path(file_storage):
    return file_storage / "test-bag_bad"


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
    assert validator.default_bagit_profile.url == "url"
    assert validator.default_bagit_profile.profile == bagit_profile_dict


@pytest.mark.parametrize(
    ("expected_valid", "external_functions"),
    ([
        (True,  []),
        (True,  ["validate", "validate_serialization"]),
        (False, ["validate"]),
        (False, ["validate_serialization"])
    ])
)
def test_get(
    profile_identifier,
    bagit_profile_dict,
    bag_path,
    external_functions,
    expected_valid
):
    """
    Test method `get` of `BagItProfilePlugin`
    with faked bagit_profile functions.
    """

    # mock external functions to return flag based on success
    patchers = []
    for f in external_functions:
        patchers.append(
            mock.patch(
                "bagit_profile.Profile." + f,
                side_effect=lambda *args, **kwargs: expected_valid
            )
        )

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict
    )

    for p in patchers:
        p.start()

    # run plugin
    result = validator.get(
        None,
        path=str(bag_path)
    )

    for p in patchers:
        p.stop()

    assert result.success

    if expected_valid:
        assert result.valid
    else:
        assert result.valid is False


def test_bagit_profile_report(
    profile_identifier,
    bagit_profile_dict,
    bag_path
):
    """
    Test the errors from the `bagit_profile.Profile` reports are properly
    written in the log of the BagItProfilePluginResult.
    """

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict
    )

    # generate fake message
    test_message = "test message"

    def fake_validate(*args, **kwargs):
        validator.default_bagit_profile.report = ProfileValidationReport()
        validator.default_bagit_profile.report.errors.append(
            ProfileValidationError(test_message)
        )
        return False
    patcher_validation = mock.patch(
        "bagit_profile.Profile.validate",
        side_effect=fake_validate
    )

    patcher_validation.start()

    # run test
    result = validator.get(
        None,
        path=str(bag_path)
    )

    patcher_validation.stop()

    error_log = result.log[Context.ERROR]
    assert len(error_log) == 2
    assert test_message in error_log[-1].body


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

    # fake bag-object
    class FakeBag:
        def __init__(self, path, info):
            self.path = path
            self.info = info
    bad_value = "bad-value"
    # fake opening Bag
    # bag-info contains two values (only "1" is allowed according to profile)
    patcher_bag = mock.patch(
        "bagit.Bag",
        side_effect=lambda *args, **kwargs: FakeBag(
            "",
            {"Property": [bad_value, "1"]}
        )
    )

    # fake validate
    patcher_validate_bag_info = mock.patch(
        "bagit_profile.Profile.validate_bag_info",
        side_effect=lambda *args, **kwargs: True
    )
    patcher_validate = mock.patch(
        "bagit_profile.Profile.validate",
        side_effect=lambda *args, **kwargs: True
    )
    # fake Path.is_file()
    patcher_path = mock.patch(
        "pathlib.Path.is_file",
        side_effect=lambda *args, **kwargs: True
    )

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict
    )

    patcher_bag.start()
    patcher_validate_bag_info.start()
    patcher_validate.start()
    patcher_path.start()

    # run plugin
    result = validator.get(
        None,
        path=str(bag_path)
    )

    assert len(result.log[Context.ERROR]) == 1
    assert "value is not allowed" in result.log[Context.ERROR][0].body
    assert bad_value in result.log[Context.ERROR][0].body

    patcher_bag.stop()
    patcher_validate_bag_info.stop()
    patcher_validate.stop()
    patcher_path.stop()


def test_get_bad_bag(
    profile_identifier,
    bagit_profile_dict,
    bag_path
):
    """
    Test method `get` of `BagItProfilePlugin` with a bag
    not containing the required manifests. The bag only contains manifests
    for sha256 and sha512.
    """

    bagit_profile_dict["Manifests-Required"] = ["md5"]

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict
    )

    # run plugin
    result = validator.get(
        None,
        path=str(bag_path)
    )

    assert result.success
    assert result.valid is False

    assert len(result.log[Context.ERROR]) == 2
    error_body = result.log[Context.ERROR][-1].body
    assert all(
        s in error_body
        for s in ["Required manifest type", "is not present in Bag."]
    )
    assert (
        bagit_profile_dict["Manifests-Required"][0]
        in result.log[Context.ERROR][-1].body
    )


def test_get_bagit_profile_exception(
    profile_identifier,
    bagit_profile_dict,
    bag_path
):
    """
    Test method `get` of `BagItProfilePlugin` when `bagit_profile.validate`
    raises an exception.
    """

    bagit_profile_exception = KeyError('Manifests-Required')
    patcher_validate = mock.patch(
        "bagit_profile.Profile.validate",
        side_effect=bagit_profile_exception
    )

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict
    )

    patcher_validate.start()

    # run plugin
    result = validator.get(
        None,
        path=str(bag_path)
    )

    patcher_validate.stop()

    assert result.success is False
    assert result.valid is None

    error_body = result.log[Context.ERROR][-1].body
    assert all(
        s in error_body
        for s in [
            type(bagit_profile_exception).__name__,
            str(bagit_profile_exception),
        ]
    )


@pytest.mark.parametrize(
    ("expected_valid", "request_profile"),
    ([
        (True,  False),
        (False, True),
    ])
)
def test_get_request_profile(
    profile_identifier,
    bagit_profile_dict,
    bag_path,
    expected_valid,
    request_profile
):
    """
    Test method `get` of `BagItProfilePlugin` with a profile_url argument.
    """

    # setup validator
    validator = BagItProfilePlugin(
        default_profile_url=profile_identifier,
        default_profile=bagit_profile_dict
    )

    # run plugin
    if request_profile:

        # fake bagit_profile.Profile.get_profile to load another profile
        user_profile = deepcopy(bagit_profile_dict)
        user_profile["Manifests-Required"] = ["md5"]
        patcher_get_profile = mock.patch(
            "bagit_profile.Profile.get_profile",
            side_effect=lambda *args, **kwargs: user_profile
        )
        patcher_get_profile.start()

        result = validator.get(
            None,
            path=str(bag_path),
            profile_url=user_profile["BagIt-Profile-Info"][
                "BagIt-Profile-Identifier"
            ],
        )

        patcher_get_profile.stop()

    else:
        result = validator.get(
            None,
            path=str(bag_path)
        )

    assert result.success
    assert result.valid == expected_valid


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
        profile_url="some_url"
    )

    assert result.success is False
    assert result.valid is None
    assert (
        result.log[Context.ERROR][-1].body
        == "Invalid request: cannot instantiate BagIt-profile"
    )
