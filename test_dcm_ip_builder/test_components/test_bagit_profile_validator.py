"""Test module for the custom `BagItProfileValidator`-class."""

import pytest

from dcm_ip_builder.components import BagItProfileValidator


def test_bagit_profile_validator_regex():
    """
    Test `load_profile` of `BagItProfileValidator` regarding LZV.nrw-specific
    description-feature ('description' should behave like 'regex').
    """

    test_profile = {"Bag-Info": {"Property": {"description": r"[0-9]*"}}}
    loaded_profile = BagItProfileValidator.load_profile(
        profile=test_profile,
    )

    assert sorted(
        list(loaded_profile["Bag-Info"]["Property"].keys())
    ) == sorted(["description", "regex"])
    assert (
        loaded_profile["Bag-Info"]["Property"]["regex"]
        == loaded_profile["Bag-Info"]["Property"]["description"]
    )


@pytest.mark.parametrize(
    ("serialization_value", "success"),
    [
        ("not_allowed_value", False),
        ("forbidden", True),
        (None, True)
    ]
)
def test_bagit_profile_validator_serialization(serialization_value, success):
    """
    Test `load_profile` of `BagItProfileValidator` regarding LZV.nrw-specific
    requirement for the value of the 'Serialization' field.
    """

    test_profile = {}
    if serialization_value is not None:
        test_profile["Serialization"] = serialization_value

    if success:
        BagItProfileValidator.load_profile(
            profile=test_profile,
        )
    else:
        assert (
            test_profile["Serialization"]
            not in BagItProfileValidator._ACCEPTED_SERIALIZATION_VALUES
        )
        with pytest.raises(ValueError) as exc_info:
            BagItProfileValidator.load_profile(
                profile=test_profile,
            )
        assert (
            f"Bad value '{serialization_value}' for 'Serialization'"
            in str(exc_info)
        )


@pytest.mark.parametrize(
    ("accept_serialization", "success"),
    [
        (None, True),
        ([], True),
        (["application/zip"], False),
    ]
)
def test_bagit_profile_validator_accept_serialization(
    accept_serialization, success
):
    """
    Test `load_profile` of `BagItProfileValidator` regarding LZV.nrw-specific
    requirement for the value of the 'Accept-Serialization' field.
    """

    test_profile = {}
    if accept_serialization is not None:
        test_profile["Accept-Serialization"] = accept_serialization

    if success:
        BagItProfileValidator.load_profile(
            profile=test_profile,
        )
    else:
        with pytest.raises(ValueError) as exc_info:
            BagItProfileValidator.load_profile(
                profile=test_profile,
            )
        assert (
            "This service does not support validation of serialized BagIt-Bags."
            in str(exc_info)
        )


@pytest.mark.parametrize(
    ("bagit_version", "success"),
    [
        (None, True),
        (["1.0"], True),
        (["0.97"], False),
        (["0.97", "1.0"], True)
    ]
)
def test_bagit_profile_validator_bagit_version(bagit_version, success):
    """
    Test `load_profile` of `BagItProfileValidator` regarding LZV.nrw-specific
    requirement for the value of the 'Accept-BagIt-Version' field.
    """

    test_profile = {}
    if bagit_version is not None:
        test_profile["Accept-BagIt-Version"] = bagit_version

    if success:
        BagItProfileValidator.load_profile(
            profile=test_profile,
        )
    else:
        with pytest.raises(ValueError) as exc_info:
            BagItProfileValidator.load_profile(
                profile=test_profile,
            )
        assert (
            "This service only supports validation with BagIt version '1.0'."
            in str(exc_info)
        )
