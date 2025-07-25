"""Test module for the significant_properties plugin."""

from shutil import copytree, copyfile
from uuid import uuid4

import pytest
from dcm_common.logger import LoggingContext as Context

from dcm_ip_builder.plugins import SignificantPropertiesPlugin


@pytest.fixture(name="xsd_schema")
def _xsd_schema():
    return "https://www.loc.gov/standards/premis/premis.xsd"


@pytest.fixture(name="duplicate_bag")
def _duplicate_bag(file_storage):
    """Duplicates "test-bag" to another directory."""
    duplicate = file_storage / str(uuid4())
    copytree(file_storage / "test-bag", duplicate)
    return duplicate


@pytest.fixture(scope="session", name="sig_prop_valid")
def _sig_prop_valid(file_storage):
    return file_storage / "significant_properties_valid.xml"


@pytest.fixture(scope="session", name="sig_prop_invalid")
def _sig_prop_invalid(file_storage):
    return file_storage / "significant_properties_invalid.xml"


@pytest.fixture(scope="session", name="sig_prop_corrupt")
def _sig_prop_corrupt(file_storage):
    return file_storage / "significant_properties_corrupt.xml"


@pytest.mark.parametrize(
    ("known_sig_prop"),
    [
        (None),
        (True)
    ],
    ids=["without known_sig_prop", "with known_sig_prop"]
)
def test_significant_properties(
    xsd_schema, duplicate_bag, sig_prop_valid, testing_config, known_sig_prop
):
    """
    Test basic validation with `SignificantPropertiesPlugin` with a valid IP.
    """

    # copy valid sig_props into 'duplicate_bag'
    copyfile(
        sig_prop_valid,
        duplicate_bag
        / testing_config.META_DIRECTORY
        / testing_config.SIGNIFICANT_PROPERTIES
    )

    # setup validator
    validator = SignificantPropertiesPlugin(
        xml_path=(
            testing_config.META_DIRECTORY
            / testing_config.SIGNIFICANT_PROPERTIES
        ),
        schema=xsd_schema,
        known_sig_prop=(
            testing_config.VALIDATION_SIGPROP_KNOWN_TYPES
            if known_sig_prop is not None
            else None
        ),
    )
    result = validator.get(None, path=str(duplicate_bag))
    assert result.success
    assert result.valid
    assert Context.WARNING in result.log
    if known_sig_prop is None:
        # 6 warnings are logged
        # since all elements in 'significant_properties.xml' are unknown
        assert len(result.log[Context.WARNING]) == 6
    else:
        # 1 warning is logged
        # for 1 unknown element in 'significant_properties.xml'
        assert len(result.log[Context.WARNING]) == 1
        assert (
            "Found a not allowed element of type 'butterfly' and value"
            in result.log[Context.WARNING][0]["body"]
        )


def test_significant_properties_invalid(
    xsd_schema, duplicate_bag, sig_prop_invalid, testing_config
):
    """
    Test basic validation with `SignificantPropertiesPlugin`
    with an invalid IP.
    """

    # copy invalid sig_props into 'duplicate_bag'
    copyfile(
        sig_prop_invalid,
        duplicate_bag
        / testing_config.META_DIRECTORY
        / testing_config.SIGNIFICANT_PROPERTIES
    )

    # setup validator
    validator = SignificantPropertiesPlugin(
        xml_path=(
            testing_config.META_DIRECTORY
            / testing_config.SIGNIFICANT_PROPERTIES
        ),
        schema=xsd_schema,
        known_sig_prop=testing_config.VALIDATION_SIGPROP_KNOWN_TYPES,
    )
    result = validator.get(None, path=str(duplicate_bag))
    assert result.success
    assert result.valid is False
    assert Context.ERROR in result.log
    assert len(result.log[Context.ERROR]) == 1
    assert (
        "Unexpected child with tag"
        in result.log[Context.ERROR][0]["body"]
    )


def test_significant_properties_corrupt(
    xsd_schema, duplicate_bag, sig_prop_corrupt, testing_config
):
    """
    Test basic validation with `SignificantPropertiesPlugin`
    with a corrupt IP.
    """

    # copy corrupted sig_props into 'duplicate_bag'
    copyfile(
        sig_prop_corrupt,
        duplicate_bag
        / testing_config.META_DIRECTORY
        / testing_config.SIGNIFICANT_PROPERTIES
    )

    # setup validator
    validator = SignificantPropertiesPlugin(
        xml_path=(
            testing_config.META_DIRECTORY
            / testing_config.SIGNIFICANT_PROPERTIES
        ),
        schema=xsd_schema,
        known_sig_prop=testing_config.VALIDATION_SIGPROP_KNOWN_TYPES,
    )
    result = validator.get(None, path=str(duplicate_bag))
    assert result.success is False
    assert result.valid is None
    assert Context.ERROR in result.log
    assert len(result.log[Context.ERROR]) == 1
    assert (
        "Malformed XML, unable to continue"
        in result.log[Context.ERROR][0]["body"]
    )
