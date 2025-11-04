"""BagIt Profile validation-plugin."""

from typing import Optional, Mapping
from pathlib import Path

import bagit_utils
from dcm_common.plugins import (
    PythonDependency,
    Signature
)
from dcm_common.logger import LoggingContext as Context
from dcm_common.util import NestedDict

from dcm_ip_builder.components import Bag
from .interface import (
    ValidationPlugin,
    ValidationPluginResult,
    ValidationPluginContext,
)


class BagItProfileValidator(bagit_utils.BagItProfileValidator):
    """
    BagIt-profiles' 'Bag-Info'-items' description fields are used as
    regex. This wrapper converts the profile to use the base-classes
    regex-validation.
    """
    @classmethod
    def load_profile(
        cls,
        profile: Optional[Mapping] = None,
        profile_src: Optional[str | Path] = None,
    ) -> dict:
        profile = super().load_profile(profile, profile_src)
        # map baginfo-description-fields into regex-fields
        for baginfo_item in profile.get("Bag-Info", {}).values():
            if "description" in baginfo_item:
                baginfo_item["regex"] = baginfo_item["description"]
        return profile


class BagItProfilePlugin(ValidationPlugin):
    """
    BagIt profile validation based on the bagit-utils library [1].

    [1] https://github.com/RichtersFinger/bagit-utils

    The constructor expects a url or local path for a BagIt-profile.
    A validation on an existing bag can be performed by means of the
    get-method by supplying a path to the bag.

    Keyword arguments:
    default_profile_url -- file path or url to the desired
                           default BagIt-profile.
    default_profile -- already instantiated BagIt-profile as dictionary
                       (default None)
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
        default_profile_url: str,
        default_profile: Optional[NestedDict] = None,
        **kwargs,
    ) -> None:

        super().__init__(**kwargs)

        self.default_profile_url = str(default_profile_url)
        self.default_profile = default_profile
        self.default_bagit_profile = BagItProfileValidator.load_profile(
            profile_src=(
                default_profile_url if default_profile is None else None
            ),
            profile=default_profile,
        )

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

        # load/validate profile
        bagit_profile = None
        bagit_profile_url = kwargs.get(
            # plugin-arg has priority
            "profile_url",
            # use baginfo as secondary
            bag.baginfo.get("BagIt-Profile-Identifier", [None])[0],
        )

        # non-default
        if bagit_profile_url is not None:
            context.result.log.log(
                Context.INFO,
                body=f"Loading profile from '{bagit_profile_url}'.",
            )
            context.set_progress("loading profile")
            context.push()
            try:
                bagit_profile = bagit_utils.BagItProfileValidator.load_profile(
                    profile_src=bagit_profile_url,
                )
            # pylint: disable=broad-exception-caught
            except Exception as exc_info:
                context.result.log.log(
                    Context.ERROR,
                    body=(
                        f"Unable to load profile '{bagit_profile_url}': "
                        + f"{exc_info}"
                    ),
                )
                context.set_progress("failure")
                context.push()

                # if a specific profile has been requested, this counts
                # as failed
                if "profile_url" in kwargs:
                    context.result.success = False
                    context.push()
                    return context.result

        # default
        if bagit_profile is None:
            bagit_profile = self.default_bagit_profile
            context.result.log.log(
                Context.INFO,
                body=(
                    "Using the default BagIt-profile "
                    f"'{self.default_profile_url}'."
                ),
            )
            context.push()

        # run validation
        context.result.log.log(Context.INFO, body=f"Validating Bag '{path}'.")
        context.set_progress(f"validating bag '{path}'")
        context.push()

        report = bagit_utils.BagValidator.validate_once(
            bag, profile=bagit_profile
        )

        # evaluate results
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
