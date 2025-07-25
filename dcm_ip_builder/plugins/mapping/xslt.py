"""Definition of the xslt-mapper plugin."""

from typing import Any, Optional
from pathlib import Path
import abc
from io import StringIO

from lxml import etree as ET
from dcm_common import LoggingContext as Context
from dcm_common.plugins import PythonDependency, Signature, Argument, JSONType

from .interface import MappingPlugin, MappingPluginContext


class XSLTMappingPlugin(MappingPlugin, metaclass=abc.ABCMeta):
    """
    Metadata mapping-plugin that works based on an xslt transformation
    provided as string.
    """

    _DISPLAY_NAME = "XSLT-Plugin"
    _NAME = "xslt-plugin"
    _DESCRIPTION = (
        "Metadata mapping based on an xslt transformation provided as string."
    )
    _DEPENDENCIES = [PythonDependency("lxml")]
    _SIGNATURE = Signature(
        path=MappingPlugin.signature.properties["path"],
        xslt=Argument(
            type_=JSONType.STRING,
            required=True,
            description=(
                "string containing the xsl-transformation (version 1.0); "
                + "see project's 'README' for details and a minimal example."
            )
        )
    )

    def _load_xslt(self, src: str) -> tuple[bool, str, Any]:
        try:
            xslt = ET.XSLT(ET.XML(src))
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            return False, f"cannot process source: {exc_info}", None
        return True, "", xslt

    def _validate_xslt(self, xslt: ET.XSLT) -> tuple[bool, str]:
        if xslt.error_log:
            return (
                False,
                (
                    "Provided 'XSLT' initialized with errors: "
                    + "".join([str(e) + "\n" for e in xslt.error_log])
                )
            )
        return True, ""

    def _validate_output(
        self, xslt_result: ET._XSLTResultTree
    ) -> tuple[bool, str, Optional[ET._ElementTree]]:
        """
        Validates the xslt output and returns an ET._ElementTree on success.
        """
        # validate produced xml string
        try:
            etree = ET.parse(StringIO(str(xslt_result)))
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            return False, (
                "The result of the 'XSLT' is not a well-formed xml: "
                + f"'{str(xslt_result)}'. "
                + f"{type(exc_info).__name__}: {str(exc_info)}."
            ), None
        if etree.getroot().tag != "metadata":
            return False, (
                "The root element after applying the 'XSLT' is "
                + f"'{etree.getroot().tag}', "
                + "instead of the expected 'metadata'."
            ), None
        return True, "", etree

    @staticmethod
    def _parse_result(etree: ET._ElementTree) -> dict:
        """
        Parse the ET._ElementTree from the xslt result.
        Returns a dictionary with pairs of values of the 'key' attribute
        and text for each element.
        """
        result = {}
        for element in etree.iter():
            # ignore root element
            if element.getparent() is None:
                continue
            # return error for nested elements
            if list(element):
                raise TypeError(
                        f"Element with tag '{element.tag}' and text "
                        + f"'{element.text}' can't have child elements "
                        + "with tags and text: "
                        + f"{[(e.tag, e.text) for e in list(element)]}."
                )
            # only process direct children of 'metadata' root element
            if element.getparent().tag == "metadata":
                if element.tag != "field":
                    raise TypeError(
                        f"Element with text '{element.text}' has "
                        + f"an unexpected tag '{element.tag}'. "
                        + "Only 'field' is allowed."
                    )
                if "key" not in element.attrib:
                    raise TypeError(
                        f"Element with tag '{element.tag}' and text "
                        + f"'{element.text}' is missing required attribute 'key'."
                    )
                additional_attributes = [
                    a for a in element.attrib.keys() if a != "key"
                ]
                if additional_attributes:
                    raise TypeError(
                        f"""Attributes '{", ".join(additional_attributes)}' """
                        + f"not allowed in element with tag '{element.tag}' "
                        + f"and text '{element.text}'."
                    )
                key = element.attrib["key"]
                value = element.text
                if key in result:
                    result[key].append(value)
                else:
                    result[key] = [value]
        return result

    def _get(self, context: MappingPluginContext, /, **kwargs):
        context.set_progress("loading xslt from string")
        context.push()
        xslt_ok, msg, xslt = self._load_xslt(kwargs["xslt"])
        if not xslt_ok:
            context.result.success = False
            context.result.log.log(
                Context.ERROR, body=f"Unable to load xslt: {msg}"
            )
            context.set_progress("failure")
            context.push()
            return context.result

        context.set_progress("validating xslt")
        context.push()
        xslt_ok, msg = self._validate_xslt(xslt)
        if not xslt_ok:
            context.result.success = False
            context.result.log.log(Context.ERROR, body=msg)
            context.set_progress("failure")
            context.push()
            return context.result

        context.result.log.log(
            Context.INFO, body=f"Mapping metadata of '{kwargs['path']}'."
        )
        context.set_progress(f"mapping metadata of '{kwargs['path']}'")
        context.push()

        # run xslt
        try:
            xslt_result = xslt(ET.parse(Path(kwargs["path"])))
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            context.result.success = False
            context.result.log.log(
                Context.ERROR,
                body=(
                    "Provided 'XSLT' encountered an error: "
                    + f"{type(exc_info).__name__}: {str(exc_info)}."
                ),
            )
            context.set_progress("failure")
            context.push()
            return context.result

        # validate output
        context.set_progress("validating xslt output")
        context.push()
        output_ok, msg, etree = self._validate_output(xslt_result)
        if not output_ok:
            context.result.success = False
            context.result.log.log(Context.ERROR, body=msg)
            context.set_progress("failure")
            context.push()
            return context.result

        # parse result
        try:
            context.result.metadata = self._parse_result(etree)
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            context.result.success = False
            context.result.log.log(
                Context.ERROR,
                body=(
                    "Failed to parse the result of the 'XSLT': "
                    + type(exc_info).__name__ + str(exc_info)
                )
            )
            context.set_progress("failure")
            context.push()
            return context.result

        context.result.success = True
        context.set_progress("success")
        context.push()
        return context.result
