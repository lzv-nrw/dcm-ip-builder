"""Definition of the demo-mapper plugin."""

import re

from dcm_common import LoggingContext as Context

from .interface import MappingPlugin, MappingPluginContext
from .util import load_xml_tree_from_file, XMLXPathMappingRule


class DemoMappingPlugin(MappingPlugin):
    """
    Demo mapping plugin for OAI-protocol XML metadata.
    """

    _DISPLAY_NAME = "Demo-Mapper-Plugin"
    _NAME = "demo"
    _DESCRIPTION = (
        "Demo-plugin for mapping XML-metadata obtained via OAI-protocol."
    )
    STATIC_METADATA = {"Source-Organization": "https://d-nb.info/gnd/0"}
    NAMESPACES = {
        "": "http://www.openarchives.org/OAI/2.0/",
        "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    LINEAR_RULES = [
        XMLXPathMappingRule(
            "./GetRecord/record/header/identifier",
            "Origin-System-Identifier",
            post_process=lambda x: (
                None if len(x) == 0 else x[0].rsplit(":", 1)[0]
            ),
            ns=NAMESPACES,
        ),
        XMLXPathMappingRule(
            "./GetRecord/record/header/identifier",
            "External-Identifier",
            post_process=lambda x: (
                None if len(x) == 0 else x[0].rsplit(":", 1)[1]
            ),
            ns=NAMESPACES,
        ),
        XMLXPathMappingRule(
            "./GetRecord/record/metadata/oai_dc:dc/dc:creator",
            "DC-Creator",
            ns=NAMESPACES,
        ),
        XMLXPathMappingRule(
            "./GetRecord/record/metadata/oai_dc:dc/dc:title",
            "DC-Title",
            ns=NAMESPACES,
        ),
        XMLXPathMappingRule(
            "./GetRecord/record/metadata/oai_dc:dc/dc:rights",
            "DC-Rights",
            ns=NAMESPACES,
        ),
        XMLXPathMappingRule(
            "./GetRecord/record/metadata/oai_dc:dc/dc:identifier",
            "DC-Terms-Identifier",
            post_process=lambda x: (
                None
                if len(x) == 0
                else [
                    identifier
                    for identifier in x
                    if identifier is not None
                    and re.search(
                        r"10\.\d{4,9}\/[-._;()/:A-Z0-9]+|urn:nbn",
                        identifier,
                        re.IGNORECASE,
                    )
                ]
            ),
            ns=NAMESPACES,
        ),
    ]

    def _get(self, context: MappingPluginContext, /, **kwargs):
        context.set_progress("parsing XML-metadata")
        context.result.log.log(
            Context.INFO,
            body=f"Loading XML-metadata from file at '{kwargs['path']}'",
        )
        context.push()
        try:
            tree = load_xml_tree_from_file(kwargs["path"])
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            context.result.success = False
            context.set_progress("failed")
            context.result.log.log(
                Context.ERROR,
                body=(
                    "Failed to load XML-metadata from file at "
                    + f"'{kwargs['path']}': {exc_info}"
                ),
            )
            context.push()
            return context.result

        context.set_progress("executing mapping-rules")
        context.push()

        context.result.metadata = self.STATIC_METADATA.copy()
        for rule in self.LINEAR_RULES:
            try:
                mapped_field = rule.map(tree)
            # pylint: disable=broad-exception-caught
            except Exception as exc_info:
                context.result.success = False
                context.set_progress("failed")
                context.result.log.log(
                    Context.ERROR,
                    body=(
                        f"Failed to map '{rule.dst}' for source "
                        + f"'{kwargs['path']}': {exc_info}"
                    ),
                )
                context.push()
                return context.result
            if mapped_field is not None and len(mapped_field) > 0:
                context.result.metadata[rule.dst] = mapped_field

        context.result.success = True
        context.set_progress("success")
        context.push()
        return context.result
