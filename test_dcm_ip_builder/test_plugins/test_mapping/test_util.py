"""Test module for mapping-plugin utility."""

from pathlib import Path
from xml.etree import ElementTree

import pytest

from dcm_ip_builder.plugins.mapping import util


@pytest.fixture(name="ns", scope="module")
def _ns():
    return {
        "": "http://lzv.nrw",
        "alternative": "http://alternative.lzv.nrw",
    }


@pytest.fixture(name="simple_xml_file", scope="module")
def _simple_xml_file(file_storage: Path, ns):
    path = file_storage / "some.xml"
    path.write_text(
        f"""<?xml version="1.0"?>
<data xmlns:alternative="{ns['alternative']}"
        xmlns="{ns['']}">
    <a>
        <value p="a">1</value>
    </a>
    <a>
        <value p="a">2</value>
    </a>
    <alternative:a>
        <value p="b">3</value>
    </alternative:a>
</data>"""
    )
    return path


def test_load_xml_tree_from_file(simple_xml_file: Path):
    """
    Test basic functionality of function 'load_xml_tree_from_file'.
    """
    tree = util.load_xml_tree_from_file(simple_xml_file)
    assert ElementTree.tostring(
        tree, encoding="utf-8"
    ) == ElementTree.tostring(
        ElementTree.fromstring(simple_xml_file.read_text(encoding="utf-8")),
        encoding="utf-8",
    )


def test_xmlmappingrule_map_minimal(simple_xml_file: Path, ns):
    """Test minimal 'XMLMappingRule.map' for simple xml-data."""
    tree = util.load_xml_tree_from_file(simple_xml_file)
    assert util.XMLMappingRule(["a", "value"], "A", ns=ns).map(tree) == [
        "1",
        "2",
    ]
    assert util.XMLMappingRule(["alternative:a", "value"], "A", ns=ns).map(
        tree
    ) == ["3"]
    assert util.XMLMappingRule(["b", "value"], "A", ns=ns).map(tree) == []


def test_xmlmappingrule_map_reduce(simple_xml_file: Path, ns):
    """Test 'XMLMappingRule.map' for simple xml-data with reducer."""
    tree = util.load_xml_tree_from_file(simple_xml_file)
    assert util.XMLMappingRule(
        ["a", "value"], "A", ns=ns, reduce=lambda x: x.attrib["p"]
    ).map(tree) == ["a", "a"]


def test_xmlmappingrule_map_post_process(simple_xml_file: Path, ns):
    """
    Test 'XMLMappingRule.map' for simple xml-data with post_process.
    """
    tree = util.load_xml_tree_from_file(simple_xml_file)
    assert util.XMLMappingRule(
        ["a", "value"], "A", ns=ns, post_process=lambda x: list(map(int, x))
    ).map(tree) == [1, 2]


def test_xmlxpathmappingrule_map_minimal(simple_xml_file: Path, ns):
    """Test minimal 'XMLXPathMappingRule.map' for simple xml-data."""
    tree = util.load_xml_tree_from_file(simple_xml_file)
    assert util.XMLXPathMappingRule("./a/value", "A", ns=ns).map(tree) == [
        "1",
        "2",
    ]
    assert util.XMLXPathMappingRule("./alternative:a/value", "A", ns=ns).map(
        tree
    ) == ["3"]
    assert util.XMLXPathMappingRule("./b/value", "A", ns=ns).map(tree) == []


def test_xmlxpathmappingrule_map_reduce(simple_xml_file: Path, ns):
    """
    Test 'XMLXPathMappingRule.map' for simple xml-data with reducer.
    """
    tree = util.load_xml_tree_from_file(simple_xml_file)
    assert util.XMLXPathMappingRule(
        "./a/value", "A", ns=ns, reduce=lambda x: x.attrib["p"]
    ).map(tree) == ["a", "a"]


def test_xmlxpathmappingrule_map_post_process(simple_xml_file: Path, ns):
    """
    Test 'XMLXPathMappingRule.map' for simple xml-data with post_process.
    """
    tree = util.load_xml_tree_from_file(simple_xml_file)
    assert util.XMLXPathMappingRule(
        "./a/value", "A", ns=ns, post_process=lambda x: list(map(int, x))
    ).map(tree) == [1, 2]
