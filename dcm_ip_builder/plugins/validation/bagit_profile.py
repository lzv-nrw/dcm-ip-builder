"""BagIt Profile validation-plugin."""

from typing import Mapping, Optional
from pathlib import Path

import bagit_utils
from dcm_common.plugins import (
    PythonDependency,
    Signature
)
from dcm_common.logger import LoggingContext as Context
from dcm_common.util import NestedDict, list_directory_content

from dcm_ip_builder.components import Bag, BagItProfileValidator
from .interface import (
    ValidationPlugin,
    ValidationPluginResult,
    ValidationPluginContext,
)


class BagValidator(bagit_utils.BagValidator):
    """Customized `bagit_utils.BagValidator`."""
    @classmethod
    def custom_validation_hook(
        # pylint: disable=unused-argument
        cls,
        bag: Bag,
        profile: Mapping,
    ) -> bagit_utils.common.ValidationReport:
        """Hook for custom validation steps."""

        # -- Validate that files in the payload directory do not differ by
        # only their capitalization.
        report = bagit_utils.common.ValidationReport(True)

        # list files in payload dir
        payload_files = list_directory_content(
            bag.path / "data",
            pattern="**/*",
            condition_function=lambda p: (p.is_file()),
        )
        # iterate files and check for multiple occurrences for
        # filename.lower()
        checked: dict[str, str] = {}
        for file in payload_files:
            file_relative = file.relative_to(bag.path)
            file_lower = str(file_relative).lower()
            if file_lower in checked:
                report.valid = False
                report.issues.append(
                    bagit_utils.common.Issue(
                        "error",
                        f"Files '{file_relative}' and '{checked[file_lower]}' "
                        "only differ in their capitalization.",
                    )
                )
            else:
                checked[file_lower] = str(file_relative)
        return report


class BagItProfilePlugin(ValidationPlugin):
    """
    BagIt profile validation based on the bagit-utils library [1].

    [1] https://github.com/RichtersFinger/bagit-utils

    The constructor expects a url or local path for a BagIt-profile.
    A validation on an existing bag can be performed by means of the
    get-method by supplying a path to the bag.

    Keyword arguments:
    supported_profiles -- mapping of URI and JSON-profile with the supported
                          BagIt-profiles.
                          Should have a match with the value of the field
                          'BagIt-Profile-Identifier' of the baginfo metadata
                          (default None leads to {})
    load_bagit_profile_from_bag -- whether to load the BagIt-Profile from bag
                                   if the URI is not included in the
                                   `supported_profiles`
                                   (default False)
    """

    _NAME = "bagit-profile"
    _DISPLAY_NAME = "BagIt-Validation-Plugin"
    _DESCRIPTION = (
        "BagIt profile validation based on the bagit-utils library."
    )
    _DEPENDENCIES = [PythonDependency("bagit-utils")]
    _SIGNATURE = Signature(
        path=ValidationPlugin.signature.properties["path"],
        profile_url=ValidationPlugin.signature.properties["profile_url"],
    )

    def __init__(
        self,
        supported_profiles: Optional[dict[str, NestedDict]] = None,
        load_bagit_profile_from_bag: bool = False,
        **kwargs,
    ) -> None:

        super().__init__(**kwargs)
        if supported_profiles is None and load_bagit_profile_from_bag is False:
            raise ValueError(
                "Failed to initialize plugin: either 'supported_profiles' "
                + "should be defined or 'load_bagit_profile_from_bag' should "
                + "be 'True'."
            )
        self.supported_profiles = supported_profiles
        self.load_bagit_profile_from_bag = load_bagit_profile_from_bag

    @classmethod
    def _validate_more(cls, kwargs):
        path = Path(kwargs["path"])
        # ensure path is a directory
        if not path.is_dir():
            return False, f"path '{path}' has to be a directory"
        return super()._validate_more(kwargs)

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

        path = Path(kwargs["path"])

        # instantiate bag
        bag = Bag(path, load=False)

        # validate bag format
        report = bag.validate_format()
        for issue in report.issues:
            match issue.level:
                case "error":
                    issue_context = Context.ERROR
                case "warning":
                    issue_context = Context.WARNING
                case _:
                    issue_context = Context.INFO
            context.result.log.log(
                issue_context, body=issue.message
            )
        if not report.valid:
            context.result.valid = False
            context.result.log.log(
                Context.INFO, body=f"Path '{path}' is not a valid BagIt-Bag."
            )
            context.push()
            return

        # load profile
        bagit_profile_uri = bag.baginfo.get(
            "BagIt-Profile-Identifier", [None]
        )[0]

        if bagit_profile_uri is None:
            context.result.log.log(
                Context.ERROR,
                body=(
                    "The tag 'BagIt-Profile-Identifier' is missing from "
                    + "the baginfo metadata."
                ),
            )
            context.result.success = False
            context.push()
            return context.result

        if (
            self.supported_profiles is not None
            and bagit_profile_uri in self.supported_profiles
        ):
            context.result.log.log(
                Context.INFO,
                body=f"Loading profile from '{bagit_profile_uri}'.",
            )
            context.set_progress("loading profile")
            context.push()
            bagit_profile = self.supported_profiles[bagit_profile_uri]
        else:
            if self.load_bagit_profile_from_bag:
                try:
                    context.result.log.log(
                        Context.INFO,
                        body=f"Loading profile from '{bagit_profile_uri}'.",
                    )
                    context.set_progress("loading profile")
                    context.push()
                    bagit_profile = BagItProfileValidator.load_profile(
                        profile_src=bagit_profile_uri,
                    )
                # pylint: disable=broad-exception-caught
                except Exception as exc_info:
                    context.result.log.log(
                        Context.ERROR,
                        body=(
                            f"Unable to load profile '{bagit_profile_uri}': "
                            + f"{exc_info}"
                        ),
                    )
                    context.result.success = False
                    context.set_progress("failure")
                    context.push()
                    return context.result
            else:
                context.result.log.log(
                    Context.ERROR,
                    body=(
                        f"The profile '{bagit_profile_uri}' is not supported. "
                        + "Consider updating the configuration of the IP "
                        + "Builder application or rebuild the IP from the "
                        + "source IE using one of the supported profiles: "
                        + f"{list(self.supported_profiles.keys())}."
                    ),
                )
                context.result.success = False
                context.push()
                return context.result

        # run validation
        context.result.log.log(Context.INFO, body=f"Validating Bag '{path}'.")
        context.set_progress(f"validating bag '{path}'")
        context.push()

        report = BagValidator.validate_once(bag, profile=bagit_profile)
        for issue in report.issues:
            match issue.level:
                case "error":
                    issue_context = Context.ERROR
                case "warning":
                    issue_context = Context.WARNING
                case _:
                    issue_context = Context.INFO
            context.result.log.log(
                issue_context, body=issue.message
            )

        # evaluate results
        if report.valid:
            context.result.valid = True
            context.result.log.log(
                Context.INFO, body=f"Bag '{path}' is valid."
            )
        else:
            context.result.valid = False
            context.result.log.log(
                Context.INFO, body=f"Bag '{path}' is invalid."
            )

        # finalize
        context.result.success = True
        context.set_progress("success")
        context.push()

        return context.result
