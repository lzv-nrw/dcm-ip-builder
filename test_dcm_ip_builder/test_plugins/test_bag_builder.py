"""Test module for the bag-builder plugins."""

from shutil import copytree, rmtree
from pathlib import Path
from unittest import mock

import pytest
import bagit_utils
from dcm_common import util, LoggingContext as Context
from dcm_common.models.data_model import get_model_serialization_test

from dcm_ip_builder.plugins import BagItBagBuilder, BagItPluginResult


@pytest.fixture(scope="session", name="working_dir")
def _working_dir(file_storage):
    return file_storage / "tmp"


@pytest.fixture(scope="session", name="test_ie")
def _test_ie(working_dir):
    return working_dir / "test-ie"


@pytest.fixture(scope="session", name="manifests")
def _manifests():
    return ["sha256", "sha512"]


@pytest.fixture(scope="session", name="tagmanifests")
def _tagmanifests():
    return ["sha256", "sha512"]


@pytest.fixture(scope="session", name="bag_info")
def _bag_info():
    return {
        "test_key": "test_value"
    }


@pytest.fixture(autouse=True)
def run_around_tests(file_storage, working_dir):

    def _cleanup(folder: Path):
        if folder.is_dir():
            rmtree(folder)

    def _copy_directory(
        source_path: str | Path,
        dest_path: str | Path
    ):
        copytree(src=source_path, dst=dest_path, dirs_exist_ok=False)

    # Run before each test starts
    # Delete folders
    _cleanup(working_dir)
    # Create expected folders
    _copy_directory(
        source_path=file_storage,
        dest_path=working_dir
    )

    # Run a test
    yield

    # Run after each test ends
    # Delete folders
    _cleanup(working_dir)


def test_BagItPluginResult(file_storage):
    """Test serialization and deserialization of model `BagItPluginResult`."""

    bag_path = file_storage / "test-bag"

    get_model_serialization_test(
        BagItPluginResult,
        (
            ((), {}),
            ((bag_path,), {}),
            ((bag_path, False), {}),
            ((), {"path": bag_path}),
            ((), {"path": bag_path, "success": False}),
            ((), {"success": True}),
        ),
    )()


@pytest.mark.parametrize(
    ("success", "src"),
    ([
        (True, "test_ie"),
        (False, "no_dir"),
    ])
)
def test_get_validate_kwargs(
    working_dir,
    bag_info,
    manifests,
    tagmanifests,
    src,
    request,
    success
):
    """
    Check the validation of the kwargs.
    """
    if src == "test_ie":
        src = request.getfixturevalue(src)

    # Create the bag
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    )
    result = test_builder.get(
        None,
        src=str(src),
        bag_info=bag_info.copy(),
    )
    assert result.success == success


def test_get_minimal(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """
    Test the get method, with the minimal requirements.
    Validate the bag version from the bagit.txt
    and the entries of bag-info.txt.
    """

    # Create the bag
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    )
    result = test_builder.get(
        None,
        src=str(test_ie),
        bag_info=bag_info.copy(),
    )

    # Read the bagit.txt
    content_bagit = (
        test_ie / "bagit.txt"
    ).read_text(encoding="utf-8")
    split_content_bagit = content_bagit.split("BagIt-Version: ")

    assert result.path is not None
    # Validate the bag version
    assert split_content_bagit[1].startswith(
        test_builder.info["bagit_version"]
    )

    bag = bagit_utils.Bag(result.path, load=False)

    # Check existence of defaults in bag-info.txt
    assert "Bagging-DateTime" in bag.baginfo
    assert "Payload-Oxum" in bag.baginfo


@pytest.mark.parametrize(
    ("inplace", "manifest_algorithms", "tagmanifest_algorithms"),
    ([
        (True, ["sha256"], ["sha256"]),
        (True, ["sha512"], ["sha256"]),
        (False, ["sha256"], ["sha256"]),
        (False, ["sha512"], ["sha256"]),
    ])
)
def test_get_diff_algorithms_for_manifests(
    working_dir,
    test_ie,
    bag_info,
    manifest_algorithms,
    tagmanifest_algorithms,
    inplace,
):
    """
    Test making a bag with different algorithms
    for the manifest and tag-manifest files.
    """

    dest = working_dir / "destination-bag"

    # Initiate the builder
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifest_algorithms,
        tagmanifests=tagmanifest_algorithms
    )

    # Create the bag
    if inplace:
        result = test_builder.get(
            None,
            src=str(test_ie),
            bag_info=bag_info.copy(),
        )
    else:
        result = test_builder.get(
            None,
            src=str(test_ie),
            bag_info=bag_info.copy(),
            dest=str(dest)
        )

    assert result.success
    assert result.path is not None
    # The bag is valid for the bagit library
    bag = bagit_utils.Bag(result.path)
    assert bag.validate_format().valid
    # Assert that only the expected_manifests and expected_tag_manifests
    # were generated
    assert set(manifest_algorithms) == set(bag.manifests.keys())
    assert set(tagmanifest_algorithms) == set(bag.tag_manifests.keys())


def test_get_inplace(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """ Test making a bag with inplace True """

    # Create the bag
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    )
    result = test_builder.get(
        None,
        src=str(test_ie),
        bag_info=bag_info.copy(),
        exist_ok=True
    )

    assert result.success
    assert result.path is not None
    # The folders inside the bag have the expected names
    folders = [x.name for x in test_ie.glob("*") if x.is_dir()]
    assert sorted(folders) == sorted(["data", "meta"])
    # The files inside the bag have the expected names
    files = [x.name for x in test_ie.glob("*") if x.is_file()]
    files.remove("bagit.txt")
    files.remove("bag-info.txt")
    assert files == [x for x in files if x.startswith(
        ("manifest", "tagmanifest"))
    ]
    # Assert the bag_info is contained in bag-info.txt
    assert (
        len(bagit_utils.Bag(test_ie, load=False).baginfo.items())
        >= len(bag_info.items())
    )


def test_get_inplace_False(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """ Test making a bag with inplace False """

    # Create the bag
    bag_path = Path(test_ie.parent) / (test_ie.name + "_bag")
    result = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    ).get(
        None,
        src=str(test_ie),
        dest=str(bag_path),
        bag_info=bag_info.copy()
    )

    assert result.success
    assert result.path is not None
    # Both folders exist, because the Bag was created with inplace False.
    assert test_ie.is_dir()
    assert bag_path.is_dir()
    # The folders inside the bag have the expected names
    folders = [x.name for x in bag_path.glob("*") if x.is_dir()]
    assert sorted(folders) == sorted(["data", "meta"])
    # The files inside the bag have the expected names
    files = [x.name for x in bag_path.glob("*") if x.is_file()]
    files.remove("bagit.txt")
    files.remove("bag-info.txt")
    assert files == [x for x in files if x.startswith(
        ("manifest", "tagmanifest"))
    ]


def test_get_existing_output_path(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """
    Test making a bag when the output_path already exists
    """

    output_path = working_dir / "test_existing_folder"

    # Create a folder named output_path in the root directory
    output_path.mkdir(exist_ok=False)

    # Attempt to make a bag and catch exception
    with pytest.raises(FileExistsError) as exc_info:
        BagItBagBuilder(
            working_dir=working_dir,
            manifests=manifests,
            tagmanifests=tagmanifests
        ).get(
            None,
            src=str(test_ie),
            dest=str(output_path),
            bag_info=bag_info.copy()
        )

    assert exc_info.type is FileExistsError
    assert str(output_path) in str(exc_info.value)


def test_get_no_data_folder(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """
    Test making a bag from a directory without a 'data' folder
    """

    # Delete the data folder
    rmtree(test_ie / "data")

    # Initiate the BagBuilder
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    )

    # Attempt to make a bag
    result = test_builder.get(
        None,
        src=str(test_ie),
        bag_info=bag_info.copy()
    )

    assert not result.success
    assert result.path is None
    assert len(result.log[Context.ERROR]) > 0


def test_get_no_meta_folder(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """
    Test making a bag from a directory without a 'meta' folder
    """

    # Delete the meta folder
    rmtree(test_ie / "meta")

    # Initiate the BagBuilder
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    )

    # Create the bag
    result = test_builder.get(
        None,
        src=str(test_ie),
        bag_info=bag_info.copy()
    )

    assert result.success
    assert result.path is not None
    # The bag is valid for the bagit library
    assert bagit_utils.Bag(result.path).validate_format().valid


def test_get_additional_baginfo_from_builder(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """
    Test the make_bag method
    to ensure it adds just two specific fields in bag-info.txt.
    """

    # Initiate the builder
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    )

    # Create the bag
    result = test_builder.get(
        None,
        src=str(test_ie),
        bag_info=bag_info.copy()
    )

    # Load the bag-info.txt
    bag_info_bag = bagit_utils.Bag(test_ie, load=False).baginfo

    assert result.success
    assert result.path is not None
    # Compare bag_info_bag with bag_info_source
    # Just three additional keys, namely Bag-Software-Agent,
    # Bagging-DateTime and Payload-Oxum.
    assert set(bag_info_bag.keys()) - set(bag_info.keys()) == {
        "Payload-Oxum", "Bagging-DateTime"
    }
    # All other entries are equal
    for key, value in bag_info.items():
        assert (
            bag_info_bag[key] == value if isinstance(value, list) else [value]
        )


def test_get_additional_root_folder(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """
    Test making a bag from a directory with an additional root folder
    """

    # Add a root folder
    (test_ie / "some_data").mkdir(parents=True, exist_ok=True)

    # Initiate the BagBuilder
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    )

    # Attempt to make a bag
    result = test_builder.get(
        None,
        src=str(test_ie),
        bag_info=bag_info.copy()
    )

    assert not result.success
    assert result.path is None
    assert len(result.log[Context.ERROR]) > 0


def test_get_no_payload(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """
    Test making a bag from an IE without payload.
    """

    # Remove payload
    for payload_file in util.list_directory_content(
        test_ie / "data",
        pattern="**/*",
        condition_function=lambda p: p.is_file()
    ):
        payload_file.unlink()

    # Initiate the BagBuilder
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    )

    # Make a bag
    result = test_builder.get(
        None,
        src=str(test_ie),
        bag_info=bag_info.copy()
    )

    assert result.success
    assert result.path is not None
    assert len(result.log[Context.WARNING]) == 1


def test_get_bagit_utils_build_error(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """
    Test making a bag when the 'bagit_utils.Bag.build_from' method
    raises an error.
    """

    # Initiate the BagBuilder
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    )

    # Make a bag and fake return of 'bagit_utils.Bag.build_from'
    bagit_utils_exception = bagit_utils.BagItError(
        "Some bagit_utils.BagItError."
    )
    with mock.patch(
        "dcm_ip_builder.plugins.bag_builder.bagit_utils.Bag.build_from",
        side_effect=bagit_utils_exception,
    ):
        result = test_builder.get(
            None, src=str(test_ie), bag_info=bag_info.copy()
        )

    assert result.success is False
    assert result.path is None
    assert str(bagit_utils_exception) in str(result.log[Context.ERROR])


def test_get_bagit_utils_validate_error(
    working_dir,
    test_ie,
    bag_info,
    manifests,
    tagmanifests
):
    """
    Test validating a bag when the 'bagit_utils.Bag.validate_format'
    method returns error in report.
    """

    # Initiate the BagBuilder
    test_builder = BagItBagBuilder(
        working_dir=working_dir,
        manifests=manifests,
        tagmanifests=tagmanifests
    )

    # repeat with validate_format
    with mock.patch(
        "dcm_ip_builder.plugins.bag_builder.bagit_utils.Bag.validate_format",
        return_value=bagit_utils.common.ValidationReport(
            False,
            [bagit_utils.common.Issue("error", "BagIt-validation error.")],
        ),
    ):
        result = test_builder.get(
            None, src=str(test_ie), bag_info=bag_info.copy()
        )

    assert result.success is False
    assert result.path is None
    assert "BagIt-validation error." in str(result.log[Context.ERROR])
