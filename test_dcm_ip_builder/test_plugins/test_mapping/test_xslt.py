"""Test xslt mapping plugin."""

import pytest
from dcm_common.logger import LoggingContext as Context

from dcm_ip_builder.plugins.mapping import XSLTMappingPlugin


@pytest.fixture(name="xslt")
def _xslt():
    return """<xsl:stylesheet version="1.0"
                xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:oai="http://www.openarchives.org/OAI/2.0/"
                xmlns:dc="http://purl.org/dc/elements/1.1/"
                xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
                exclude-result-prefixes="xs xsl oai dc oai_dc">
    <xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>

    <xsl:variable name="oai_id" select="//oai:record/oai:header/oai:identifier"/>

    <xsl:template match="/">
        <metadata>

            <field>
                <xsl:attribute name="key">
                    <xsl:text>Source-Organization</xsl:text>
                </xsl:attribute>
                <xsl:text>https://d-nb.info/gnd/0</xsl:text>
            </field>

            <field>
                <xsl:attribute name="key">
                    <xsl:text>Origin-System-Identifier</xsl:text>
                </xsl:attribute>
                <xsl:value-of select="concat(substring-before($oai_id,':'), ':', substring-before(substring-after($oai_id,':'), ':'))" />
            </field>

            <field>
                <xsl:attribute name="key">
                    <xsl:text>External-Identifier</xsl:text>
                </xsl:attribute>
                <xsl:value-of select="substring-after(substring-after($oai_id,':'), ':')" />
            </field>

            <xsl:apply-templates select="//oai_dc:dc"/>
        </metadata>
    </xsl:template>

    <xsl:template match="//oai_dc:dc">

        <xsl:for-each select="//dc:title">
            <field>
                <xsl:attribute name="key">
                    <xsl:text>DC-Title</xsl:text>
                </xsl:attribute>
                <xsl:value-of select="."/>
            </field>
        </xsl:for-each>

        <xsl:for-each select="//dc:creator">
            <field>
                <xsl:attribute name="key">
                    <xsl:text>DC-Creator</xsl:text>
                </xsl:attribute>
                <xsl:value-of select="."/>
            </field>
        </xsl:for-each>

        <xsl:for-each select="//dc:rights">
            <field>
                <xsl:attribute name="key">
                    <xsl:text>DC-Rights</xsl:text>
                </xsl:attribute>
                <xsl:value-of select="."/>
            </field>
        </xsl:for-each>

    </xsl:template>
</xsl:stylesheet>
    """


@pytest.fixture(name="expected_bag_info")
def _expected_bag_info():
    return {
        "Source-Organization": ["https://d-nb.info/gnd/0"],
        "Origin-System-Identifier": ["test:oai_dc"],
        "External-Identifier": ["d2d5513f-0ed1-4db5-a489-aa4c33eb8325"],
        "DC-Creator": ["Thistlethwaite, Bartholomew"],
        "DC-Title": [
            "Decoding the Butterfly Effect: When a Chaos changes the world"
        ],
        "DC-Rights": ["CC BY-NC 4.0", "info:eu-repo/semantics/openAccess"],
    }


def test_xsltplugin_minimal(fixtures, expected_bag_info, xslt):
    """Test xslt-plugin mapping for typical setup."""
    result = XSLTMappingPlugin().get(
        None,
        path=fixtures / "ie-demo-import" / "source_metadata.xml",
        xslt=xslt,
    )

    assert result.success
    assert result.metadata == expected_bag_info


def test_xslt_plugin_missing_title(fixtures, expected_bag_info, xslt):
    """
    Test xslt-plugin mapping for metadata that is missing a dc-title.
    """
    bag_info = (
        XSLTMappingPlugin()
        .get(
            None,
            path=fixtures
            / "ie-demo-import"
            / "source_metadata_missing_title.xml",
            xslt=xslt,
        )
        .metadata
    )
    del expected_bag_info["DC-Title"]
    assert bag_info == expected_bag_info


@pytest.mark.parametrize(
    ("xslt_string", "expected_errors"),
    (
        [
            (
                """<xsl:stylesheet version="1.0"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
            exclude-result-prefixes="xs xsl">
   <xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
   <xsl:template match="/">
      <metadata>
      </metadata>
   </xsl:template>
</xsl:stylesheet>
""",
                [],
            ),  # success
            (
                """<xsl:stylesheet version="1.0"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
            exclude-result-prefixes="xsl">
   <xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
   <xsl:template match="/">
      <metadata>
      </metadata>
   </xsl:template>
</xsl:stylesheet>
""",
                [],
            ),  # success (output with namespace prefix)
            (
                """<xsl:stylesheet version="1.0"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
            exclude-result-prefixes="xsl">
   <xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
   <xsl:template match="/">
      <metadata>
        <otherfield>
        </otherfield>
      </metadata>
   </xsl:template>
</xsl:stylesheet>
""",
                ["unexpected tag 'otherfield'"],
            ),  # element tag different from 'field'
            (
                """<xsl:stylesheet version="1.0"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
            exclude-result-prefixes="xsl">
   <xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
   <xsl:template match="/">
      <metadata>
        <field>
        </field>
      </metadata>
   </xsl:template>
</xsl:stylesheet>
""",
                ["missing required attribute 'key'"],
            ),  # missing 'key' attribute
            (
                """<xsl:stylesheet version="1.0"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
            exclude-result-prefixes="xsl">
   <xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
   <xsl:template match="/">
      <metadata>
        <field key="string" attr="string">
        </field>
      </metadata>
   </xsl:template>
</xsl:stylesheet>
""",
                ["Attributes 'attr' not allowed in element"],
            ),  # not allowed attribute
            (
                """<xsl:stylesheet version="1.0"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
            exclude-result-prefixes="xsl">
   <xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
   <xsl:template match="/">
      <metadata>
        <field key="string">
            <child-field>
            </child-field>
        </field>
      </metadata>
   </xsl:template>
</xsl:stylesheet>
""",
                ["can't have child elements"],
            ),  # child elements
            (
                """<xsl:stylesheet version="1.0"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
            exclude-result-prefixes="xs xsl">
   <xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
   <xsl:variable name="oai_id" select="//oai:record/oai:header/oai:identifier"/>
   <xsl:template match="/">
      <metadata>
      </metadata>
   </xsl:template>
</xsl:stylesheet>
""",
                ["Provided 'XSLT' encountered an error"]
            ),  # missing namespace for variable definition
            (
                """<xsl:stylesheet version="1.0"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
            exclude-result-prefixes="xs xsl">
   <xsl:output method="text" version="1.0" encoding="UTF-8" indent="yes"/>
   <xsl:template match="/">
      <metadata>
      </metadata>
   </xsl:template>
</xsl:stylesheet>
""",
                ["The result of the 'XSLT' is not a well-formed xml"],
            ),  # wrong xsl:output method
            (
                """<xsl:stylesheet version="1.0"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
            exclude-result-prefixes="xs xsl">
   <xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
   <xsl:template match="/">
        <field>
        </field>
   </xsl:template>
</xsl:stylesheet>
""",
                ["The root element after applying the 'XSLT'"],
            ),  # missing 'metadata' root element
            (
                """<xsl:stylesheet version="2.0"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
            exclude-result-prefixes="xs xsl">
   <xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
   <xsl:template match="/">
      <metadata>
      </metadata>
   </xsl:template>
</xsl:stylesheet>
""",
                ["Provided 'XSLT' initialized with errors"],
            ),  # non-supported xslt version
            (
                "some xslt transformation",
                ["Unable to load xslt: cannot process source"],
            ),  # no xsl string
        ]
    ),
    ids=[
        "success",
        "success (output with namespace prefix)",
        "element tag different from 'field'",
        "missing 'key' attribute",
        "not allowed attribute",
        "child elements",
        "missing namespace for variable definition",
        "wrong output method",
        "missing 'metadata' root element",
        "non-supported xslt version",
        "no xsl string",
    ]
)
def test_xsltplugin_errors(fixtures, xslt_string, expected_errors):
    """Test xslt-plugin mapping for typical errors in the xsl file."""

    result = XSLTMappingPlugin().get(
        None,
        path=fixtures / "ie-demo-import" / "source_metadata.xml",
        xslt=xslt_string,
    )

    if expected_errors:
        assert not result.success
        assert Context.ERROR in result.log
        print(result.log.fancy())
        assert len(result.log[Context.ERROR]) == len(expected_errors)
        for idx, error in enumerate(expected_errors):
            assert error in result.log[Context.ERROR][idx]["body"]
    else:
        assert result.success
        assert Context.ERROR not in result.log
        assert result.metadata == {}
