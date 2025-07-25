"""Significant Properties validation-plugin."""

from typing import Optional
from pathlib import Path
from xml.etree.ElementTree import fromstring

from dcm_common import LoggingContext as Context
from dcm_common.xml import XMLValidator, XML
from dcm_common.plugins import Signature, Argument, JSONType, PythonDependency

from .interface import (
    ValidationPlugin,
    ValidationPluginResult,
    ValidationPluginContext,
)


class SignificantPropertiesPlugin(ValidationPlugin):
    """
    Significant properties validation.

    Keyword arguments:
    xml_path -- relative path to the significant_properties.xml file
    schema -- xsd schema as either string, url, or Path
    schema_name -- name identifier that is used in the log
                   (default None)
    version -- optionally request specific XML schema version ('1.0' or
               '1.1')
               (default None; uses `xmlschema`s default, 1.0)
    known_sig_prop -- list of known elements for the significant_properties;
                      a warning is logged for any unknown element
    """

    _NAME = "significant-properties"
    _DISPLAY_NAME = "SigProp-Validation-Plugin"
    _DESCRIPTION = "Significant properties validation."
    _DEPENDENCIES = [PythonDependency("xmlschema")]
    _SIGNATURE = Signature(
        path=Argument(
            type_=JSONType.STRING,
            required=True,
            description="target file for validation",
            example="relative/path/to/file",
        )
    )
    _SIGPROP_PREMIS_NAMESPACE = "{http://www.loc.gov/premis/v3}"

    def __init__(
        self,
        xml_path: Path,
        schema: XML,
        version: Optional[str] = None,
        schema_name: Optional[str] = None,
        known_sig_prop: Optional[list[str]] = None,
        **kwargs,
    ) -> None:

        super().__init__(**kwargs)

        self.xml_path = xml_path
        self.sig_prop_validator = XMLValidator(
            schema=schema,
            version=version,
            schema_name=schema_name
        )
        self.known_sig_prop = known_sig_prop or []

    def _validate_significant_properties(self, path: Path) -> list[str]:
        """
        Validates the elements in the 'significant_properties' xml file
        against a list of known elements.

        Returns a list of messages to be logged.
        """
        msgs = []
        et = fromstring(path.read_text(encoding="utf-8"))
        try:
            significant_properties = et.find(
                f"{self._SIGPROP_PREMIS_NAMESPACE}object"
            ).findall(
                f"{self._SIGPROP_PREMIS_NAMESPACE}significantProperties"
            )
        except AttributeError:
            return msgs
        for p in significant_properties:
            _type = p.find(
                f"{self._SIGPROP_PREMIS_NAMESPACE}significantPropertiesType"
            ).text
            if _type not in self.known_sig_prop:
                _value = p.find(
                    f"{self._SIGPROP_PREMIS_NAMESPACE}significantPropertiesValue"
                ).text
                msgs.append(
                    f"Found a not allowed element of type '{_type}' and "
                    + f"value '{_value}' in file '{path}'."
                )
        return msgs

    def _get(
        self, context: ValidationPluginContext, /, **kwargs
    ) -> ValidationPluginResult:

        # validate whether request is ok
        valid, msg = self.validate(kwargs)
        if not valid:
            context.result.log.log(
                Context.ERROR,
                body=f"Invalid request: {msg}",
            )
            context.result.success = False
            return context.result

        sig_prop_path = Path(kwargs["path"]) / self.xml_path

        if not sig_prop_path.is_file():
            context.result.log.log(
                Context.INFO,
                body=(
                    f"File '{sig_prop_path}' does not exist. "
                    + "Skipping validation."
                )
            )
            context.result.valid = True
            context.result.success = True
            context.set_progress("success")
            context.push()
            return context.result

        context.result.log.log(
            Context.INFO, body=f"Validating file '{sig_prop_path}'."
        )
        context.set_progress(f"validating file '{sig_prop_path}'")
        context.push()

        # perform validation
        validator_result = self.sig_prop_validator.validate(
            xml=sig_prop_path,
            xml_name=sig_prop_path.name
        )

        # claim and add merge messages from the sig_prop_validator
        for _context in validator_result.log.report.keys():
            for msg in validator_result.log[_context]:
                msg.claim(self._DISPLAY_NAME)
        context.result.log.merge(validator_result.log)
        context.push()

        if validator_result.success:

            # validate existing fields and add warning for unknown fields
            warnings = self._validate_significant_properties(sig_prop_path)
            if warnings:
                context.result.log.log(
                    Context.WARNING, body=warnings
                )

            # evaluate results
            if Context.ERROR not in context.result.log:
                context.result.valid = True
                context.result.log.log(
                    Context.INFO, body=f"File '{sig_prop_path}' is valid."
                )
            else:
                context.result.valid = False
                context.result.log.log(
                    Context.INFO, body=f"File '{sig_prop_path}' is invalid."
                )

            context.result.success = True
            context.set_progress("success")
            context.push()
        else:
            context.result.log.log(
                Context.INFO,
                body=f"Validation of file '{sig_prop_path}' failed."
            )
            context.result.success = False
            context.set_progress("failure")
            context.push()

        return context.result
