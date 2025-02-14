from pathlib import Path

from dcm_ip_builder.plugins.mapping import GenericMapper, util


class ExternalMapper(GenericMapper):
    """Mapper for OAI-protocol to BagIt-metadata."""

    NAMESPACES = {
        "": "http://www.openarchives.org/OAI/2.0/",
        "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    RULE = util.XMLXPathMappingRule(
        "./GetRecord/record/metadata/oai_dc:dc/dc:title",
        "DC-Title",
        ns=NAMESPACES,
    )

    def get_metadata(self, path, /, **kwargs):
        tree = util.load_xml_tree_from_file(Path(path))
        title = self.RULE.map(tree)
        if not title:
            raise ValueError("Source metadata missing title-information.")
        return {self.RULE.dst: title}
