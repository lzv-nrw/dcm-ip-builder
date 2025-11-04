"""Test-module for build-endpoint."""

from pathlib import Path
from shutil import copytree
from uuid import uuid4

import pytest
from lxml import etree as et
from dcm_common.util import list_directory_content

from dcm_ip_builder import app_factory
from dcm_ip_builder.components import Bag


@pytest.fixture(name="minimal_request_body")
def _minimal_request_body():
    return {
        "build": {
            "target": {"path": str("test-ie")},
            "mappingPlugin": {"plugin": "demo", "args": {}},
        }
    }


@pytest.fixture(name="duplicate_ie")
def _duplicate_ie(file_storage, testing_config):
    """Duplicates "test-ie" to another directory."""
    duplicate = testing_config.FS_MOUNT_POINT / str(uuid4())
    copytree(file_storage / "test-ie", duplicate)
    return duplicate


def test_build_minimal(testing_config, minimal_request_body, test_bag_baginfo):
    """Test basic functionality of /build-POST endpoint."""

    app = app_factory(testing_config())
    client = app.test_client()

    # submit job
    response = client.post("/build", json=minimal_request_body)

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # wait until job is completed
    app.extensions["orchestra"].stop(stop_on_idle=True)
    report = client.get(f"/report?token={token}").json

    assert (testing_config.FS_MOUNT_POINT / report["data"]["path"]).is_dir()
    assert Bag(
        testing_config.FS_MOUNT_POINT / report["data"]["path"], load=False
    ).validate_format().valid
    assert report["data"]["valid"]
    assert report["data"]["success"]
    assert report["data"]["originSystemId"] == "id"
    assert report["data"]["externalId"] == "0"
    assert report["data"]["sourceOrganization"] == "https://d-nb.info/gnd/0"
    assert isinstance(report["data"]["bagInfoMetadata"], dict)
    assert sorted(list(report["data"]["bagInfoMetadata"].keys())) == sorted(
        list(test_bag_baginfo.keys())
    )
    assert "BagIt-Validation-Plugin" in str(report["log"])


def test_build_minimal_no_validation(testing_config, minimal_request_body):
    """
    Test basic functionality of /build-POST endpoint without validation.
    """

    app = app_factory(testing_config())
    client = app.test_client()

    # submit job
    minimal_request_body["build"]["validate"] = False
    response = client.post("/build", json=minimal_request_body)

    # wait until job is completed
    app.extensions["orchestra"].stop(stop_on_idle=True)
    report = client.get(f"/report?token={response.json['value']}").json

    assert (testing_config.FS_MOUNT_POINT / report["data"]["path"]).is_dir()
    assert "valid" not in report["data"]
    assert "originSystemId" not in report["data"]
    assert "externalId" not in report["data"]
    assert "sourceOrganization" not in report["data"]
    assert "bagInfoMetadata" not in report["data"]
    assert report["data"]["success"]
    assert "BagIt-Validation-Plugin" not in str(report["log"])


def test_build_missing_meta(
    file_storage, minimal_request_body, testing_config
):
    """Test /build-POST with missing metadata."""

    app = app_factory(testing_config())
    client = app.test_client()

    # submit job
    minimal_request_body["build"]["target"]["path"] = str(
        Path(minimal_request_body["build"]["target"]["path"]).parent
        / "test-ie-missing-meta"
    )

    response = client.post("/build", json=minimal_request_body)

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    app.extensions["orchestra"].stop(stop_on_idle=True)
    report = client.get(f"/report?token={token}").json

    # output is invalid
    assert not report["data"]["success"]
    assert len(report["log"]["ERROR"]) == 2
    assert "valid" not in report["data"]

    # directory for fs-hook exists but is empty
    assert "path" in report["data"]
    assert (file_storage / report["data"]["path"]).exists()
    assert (
        len(list_directory_content(file_storage / report["data"]["path"])) == 0
    )


@pytest.mark.parametrize(
    ("ie", "dcxml_exists"),
    [("test-ie", True), ("test-ie-mets", False)],
    ids=["dc-metadata", "mets-metadata"],
)
def test_build_dc_xml(ie, dcxml_exists, testing_config, minimal_request_body):
    """Test basic functionality of /build-POST endpoint."""

    app = app_factory(testing_config())
    client = app.test_client()

    # submit job
    minimal_request_body["build"]["target"]["path"] = str(
        Path(minimal_request_body["build"]["target"]["path"]).parent / ie
    )

    response = client.post("/build", json=minimal_request_body)

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    app.extensions["orchestra"].stop(stop_on_idle=True)
    report = client.get(f"/report?token={token}").json

    # output of attempt should exist
    output_path = testing_config.FS_MOUNT_POINT / report["data"]["path"]
    assert output_path.is_dir()
    output_bag = Bag(output_path)
    dcxml = (
        testing_config.FS_MOUNT_POINT
        / report["data"]["path"]
        / testing_config.META_DIRECTORY
        / testing_config.DC_METADATA
    )
    assert dcxml.is_file() == dcxml_exists
    if dcxml_exists:
        assert all(
            "meta/dc.xml" in output_bag.tag_manifests[tag]
            for tag in output_bag.tag_manifests
        )
        parser = et.XMLParser(remove_blank_text=True)
        src_tree = et.parse(dcxml, parser)
        title = src_tree.find(".//{http://purl.org/dc/elements/1.1/}title")
        creator = src_tree.find(".//{http://purl.org/dc/elements/1.1/}creator")
        assert title.text == "Some title"
        assert creator.text == "Max Muster, et al."
        assert report["data"]["success"]
        assert report["data"]["valid"]
    else:
        assert not all(
            "meta/dc.xml" in output_bag.tag_manifests[tag]
            for tag in output_bag.tag_manifests
        )
        assert not report["data"]["success"]
        assert not report["data"]["valid"]


@pytest.mark.parametrize(
    ("validate_flag"),
    [(False), (True)],
    ids=["validate_False", "validate_True"],
)
def test_build_no_payload(
    minimal_request_body,
    duplicate_ie,
    testing_config,
    validate_flag,
):
    """Test /build-POST for an IE without payload."""

    app = app_factory(testing_config())
    client = app.test_client()

    # Remove payload
    for payload_file in list_directory_content(
        duplicate_ie / "data",
        pattern="**/*",
        condition_function=lambda p: p.is_file(),
    ):
        payload_file.unlink()

    # submit job
    minimal_request_body["build"]["target"]["path"] = str(
        Path(minimal_request_body["build"]["target"]["path"]).parent
        / duplicate_ie.name
    )
    minimal_request_body["build"]["validate"] = validate_flag

    response = client.post("/build", json=minimal_request_body)

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    app.extensions["orchestra"].stop(stop_on_idle=True)
    report = client.get(f"/report?token={token}").json

    # success depends on whether validation is performed
    assert report["data"]["success"] == (not validate_flag)
    # output exists and is a valid 'bagit_utils.Bag'
    assert "path" in report["data"]
    assert (testing_config.FS_MOUNT_POINT / report["data"]["path"]).exists()
    assert Bag(
        testing_config.FS_MOUNT_POINT / report["data"]["path"]
    ).validate().valid

    # a warning is included in the log from the bag-builder
    assert len(report["log"]["WARNING"]) >= 1
    assert any(
        "Bag contains no payload."
        in m["body"]
        for m in report["log"]["WARNING"]
    )

    if validate_flag:
        assert report["data"]["valid"] is False
        assert report["data"]["details"]["bagit-profile"]["valid"]
        assert report["data"]["details"]["significant-properties"]["valid"]
        assert report["data"]["details"]["payload-structure"]["valid"] is False
