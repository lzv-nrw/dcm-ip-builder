import pytest

from dcm_ip_builder.plugins.mapping import DemoMappingPlugin


@pytest.fixture(name="expected_bag_info")
def _expected_bag_info():
    return {
        "Source-Organization": "https://d-nb.info/gnd/0",
        "Origin-System-Identifier": "test:oai_dc",
        "External-Identifier": "d2d5513f-0ed1-4db5-a489-aa4c33eb8325",
        "DC-Creator": ["Thistlethwaite, Bartholomew"],
        "DC-Title": [
            "Decoding the Butterfly Effect: When a Chaos changes the world"
        ],
        "DC-Rights": ["CC BY-NC 4.0", "info:eu-repo/semantics/openAccess"],
    }


def test_demo_plugin_minimal(fixtures, expected_bag_info):
    """Test demo-plugin mapping for typical setup."""
    bag_info = (
        DemoMappingPlugin()
        .get(None, path=fixtures / "ie-demo-import" / "source_metadata.xml")
        .metadata
    )
    assert bag_info == expected_bag_info


def test_demo_plugin_missing_title(fixtures, expected_bag_info):
    """
    Test demo-plugin mapping for metadata that is missing a dc-title.
    """
    bag_info = (
        DemoMappingPlugin()
        .get(
            None,
            path=fixtures
            / "ie-demo-import"
            / "source_metadata_missing_title.xml",
        )
        .metadata
    )
    del expected_bag_info["DC-Title"]
    assert bag_info == expected_bag_info
