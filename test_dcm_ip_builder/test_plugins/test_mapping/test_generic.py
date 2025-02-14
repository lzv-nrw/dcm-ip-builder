"""Test generic mapping plugins."""

from base64 import b64encode

import dill
from dcm_common import LoggingContext as Context

from dcm_ip_builder.plugins.mapping import (
    GenericMapper,
    GenericB64Plugin,
    GenericUrlPlugin,
)


def test_generic_b64_minimal():
    """Test generic-base64-mapping"""

    class Mapper(GenericMapper):
        def get_metadata(self, path, /, **kwargs):
            return kwargs

    result = GenericB64Plugin().get(
        None,
        path="<source-file>",
        mapper={
            "base64": b64encode(dill.dumps(Mapper)),
            "args": {"field-1": "value-1"},
        },
    )

    assert result.metadata == {"field-1": "value-1"}


def test_generic_url_minimal(fixtures):
    """Test generic-url-mapping"""
    result = GenericUrlPlugin().get(
        None,
        path="<source-file>",
        mapper={
            "url": f"file://{(fixtures / 'plugins' / 'm.py').resolve()}",
            "args": {"field-1": "value-1"},
        },
    )

    assert result.metadata == {"field-1": "value-1"}


def test_generic_url_docs(fixtures):
    """Test generic-url-mapping for docs-example"""
    result = GenericUrlPlugin().get(
        None,
        path=str(fixtures / "ie-demo-import" / "source_metadata.xml"),
        mapper={
            "url": f"file://{(fixtures / 'plugins' / 'm2.py').resolve()}",
            "args": {},
        },
    )

    assert result.success
    assert result.metadata == {
        "DC-Title": [
            "Decoding the Butterfly Effect: When a Chaos changes the world"
        ]
    }


def test_generic_url_docs_bad(fixtures):
    """Test generic-url-mapping for docs-example"""
    result = GenericUrlPlugin().get(
        None,
        path=str(
            fixtures / "ie-demo-import" / "source_metadata_missing_title.xml"
        ),
        mapper={
            "url": f"file://{(fixtures / 'plugins' / 'm2.py').resolve()}",
            "args": {},
        },
    )

    assert not result.success
    assert result.metadata is None
    assert Context.ERROR in result.log
