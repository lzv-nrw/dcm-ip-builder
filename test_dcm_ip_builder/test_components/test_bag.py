"""Test module for the custom `Bag`-class."""

from shutil import copytree
from uuid import uuid4

from dcm_ip_builder.components import Bag


def test_bag_set_baginfo(fixtures, file_storage):
    """Test method `Bag.set_baginfo`."""

    # make copy of bag from fixtures
    bag_dir = file_storage / str(uuid4())
    copytree(fixtures / "test-bag", bag_dir)

    bag = Bag(bag_dir, load=False)

    # update baginfo with mixed value-types
    bag.set_baginfo({"a": ["list", "of", "strings"], "b": "no-list"})

    # validate
    assert bag.validate_format().valid
    assert bag.baginfo == {"a": ["list", "of", "strings"], "b": ["no-list"]}


def test_bag_custom_validate_format_hook_no_payload(fixtures, file_storage):
    """
    Test method `Bag.custom_validate_format_hook` regarding missing
    payload.
    """

    # make copy of bag from fixtures
    bag_dir = file_storage / str(uuid4())
    copytree(fixtures / "test-bag", bag_dir)

    bag = Bag(bag_dir, load=False)

    # delete payload and refresh manifests
    for f in (bag_dir / "data").glob("**/*"):
        if f.is_file():
            f.unlink()

    bag.set_manifests()
    bag.set_tag_manifests()

    # run validation
    report = bag.validate_format()

    assert report.valid
    assert len(report.issues) == 1
    assert report.issues[0].level == "warning"
    print(report.issues[0].message)
