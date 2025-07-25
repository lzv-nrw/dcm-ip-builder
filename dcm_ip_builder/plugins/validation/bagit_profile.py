"""BagIt Profile validation-plugin based on the `bagit-profile` library."""

from typing import Optional
import re
from pathlib import Path

from bagit_profile import Profile, ProfileValidationError
import bagit
from dcm_common.plugins import (
    PythonDependency,
    Signature
)
from dcm_common.logger import LoggingContext as Context
from dcm_common.util import NestedDict

from .interface import (
    ValidationPlugin,
    ValidationPluginResult,
    ValidationPluginContext,
)


# ------------------------------------------------------------------------
# FIXME this provisional patch does not actually "understand" the core-
# issuewhen running many jobs in sequence, the execution of Jobs could
# freeze on call of 'logging.error'
# pylint: disable=wrong-import-order
from urllib.request import urlopen
import sys
import json


class PatchedProfile(Profile):
    """Patched to avoid potential deadlock on 'logging.error'."""
    def get_profile(self):
        try:
            f = urlopen(self.url)
            profile = f.read()
            if sys.version_info > (3,):
                profile = profile.decode("utf-8")
            profile = json.loads(profile)
        except Exception as e:  # pylint: disable=broad-except
            print("Cannot retrieve profile from %s: %s", self.url, e)
            # this can cause deadlocks for some reason..
            # logging.error("Cannot retrieve profile from %s: %s", self.url, e)
            # This is a fatal error.
            sys.exit(1)

        return profile
# ------------------------------------------------------------------------


class BagItProfilePlugin(ValidationPlugin):
    """
    BagIt profile validation based on the BagIt Profile library [1].

    [1] https://github.com/bagit-profiles/bagit-profiles-validator

    The constructor expects a url or local path for a BagIt-profile.
    A validation on an existing bag can be performed by means of the
    get-method by supplying a path to the bag.

    Keyword arguments:
    default_profile_url -- file path or url to the desired
                           default BagIt-profile.
    default_profile -- already instantiated BagIt-profile as dictionary
                       (default None)
    baginfo_tag_case_sensitive -- whether to use case sensitive tags
                                  in profile (default True)
    """

    _NAME = "bagit-profile"
    _DISPLAY_NAME = "BagIt-Validation-Plugin"
    _DESCRIPTION = (
        "BagIt profile validation based on the bagit-profile library."
    )
    _DEPENDENCIES = [PythonDependency("bagit_profile")]
    _SIGNATURE = Signature(
        path=ValidationPlugin.signature.properties["path"],
        profile_url=ValidationPlugin.signature.properties["profile_url"],
    )

    def __init__(
        self,
        default_profile_url: str,
        default_profile: Optional[NestedDict] = None,
        baginfo_tag_case_sensitive: bool = True,
        **kwargs,
    ) -> None:

        super().__init__(**kwargs)

        self.default_profile_url = str(default_profile_url)
        self.default_profile = default_profile
        self.ignore_baginfo_tag_case = not baginfo_tag_case_sensitive
        self.default_bagit_profile = PatchedProfile(
            url=self.default_profile_url,
            profile=self.default_profile,
            ignore_baginfo_tag_case=self.ignore_baginfo_tag_case,
        )

    @classmethod
    def _validate_more(cls, kwargs):
        # ensure path is a directory
        if not Path(kwargs["path"]).is_dir():
            return False, "'path' has to be a directory"
        # ensure path is a BagIt bag
        try:
            bagit.Bag(kwargs["path"])
        except bagit.BagError:
            return False, "'path' is not a valid path to a BagIt bag"
        if "profile_url" in kwargs:
            # ensure bagit_profile.Profile can be instantiated
            try:
                PatchedProfile(
                    url=kwargs["profile_url"],
                    profile=None
                )
            except (SystemExit, ProfileValidationError):
                # `get_profile` method of `Profile` raises a sys.exit(1)
                # if it cannot retrieve the profile
                return False, "cannot instantiate BagIt-profile"
        return super()._validate_more(kwargs)

    def _validate_serialization(
        self, path: str | Path, bagit_profile: Profile
    ) -> tuple[bool, list[str]]:
        """
        This method validates the bag serialization.

        Returns tuple of boolean for validity and a list of errors as strings.

        Keyword arguments:
        path -- path to the bag to be validated
        bagit_profile -- Profile against which to validate bag
        """
        if bagit_profile.validate_serialization(path):
            return True, []
        return False, [f"'{path}': Payload serialization is not ok."]

    def _validate_bagit_profile(
        self, bag: bagit.Bag, bagit_profile: Profile
    ) -> tuple[Optional[bool], list[str]]:
        """
        This method validates the bag against the validator's BagIt-profile.

        Returns tuple of boolean for validity and a list of errors as strings.

        Keyword arguments:
        bag -- the bag to be validated
        bagit_profile -- Profile against which to validate bag
        """

        try:
            validation = bagit_profile.validate(bag)
        except Exception as exc:  # pylint: disable=broad-except
            # execution failed
            return None, [
                f"An exception of type '{type(exc).__name__}' occurred {exc}."
            ]

        if validation:
            return True, []

        errors = []
        errors.append(f"'{bag.path}': Bag does not conform to profile.")
        # rewrite error messages from `bagit_profile`
        if bagit_profile.report:
            # mypy - hint
            assert bagit_profile.report is not None
            # add `bagit_profile` internally logged errors to Logger
            for e in bagit_profile.report.errors:
                errors.append(
                    e.value.replace(f"{bag.path}: ", f"'{bag.path}': ")
                )
        return False, errors

    def _validate_bag_info(
        self, bag: bagit.Bag, bagit_profile: Profile
    ) -> tuple[bool, list[str]]:
        """
        This method validates bag-info.txt against the validator's
        BagIt-profile.

        Returns tuple of boolean for validity and a list of errors as strings.

        This method performs checks for the bag-info.txt using regex
        which are not performed by the `bagit_profile.validate_bag_info` method
        (executed with `bagit_profile.validate`).

        Keyword arguments:
        bag -- the bag to be validated
        bagit_profile -- Profile against which to validate bag
        """

        errors = []

        # perform custom tests in the same format as in the
        # `bagit_profile.validate_bag_info` method
        # to this end, first repeat collection of bag_info
        # (duplicated from bagit-profile library)
        # First, check to see if bag-info.txt exists.
        path_to_baginfotxt = Path(bag.path) / "bag-info.txt"
        if not path_to_baginfotxt.is_file():
            errors.append(f"'{bag.path}': 'bag-info.txt' is not present.")

        # now test format of description tags
        if bagit_profile.ignore_baginfo_tag_case:
            bag_info = {
                bagit_profile.normalize_tag(k): v for k, v in bag.info.items()
            }
        else:
            bag_info = bag.info

        for tag in bagit_profile.profile["Bag-Info"]:
            normalized_tag = bagit_profile.normalize_tag(tag)
            config = bagit_profile.profile["Bag-Info"][tag]
            if "description" in config and normalized_tag in bag_info:
                # enter all values into a list to check with description
                # individually afterwards
                if isinstance(bag_info[normalized_tag], list):
                    values = bag_info[normalized_tag]
                else:
                    values = [bag_info[normalized_tag]]
                # now check for matching regex/description
                for value in values:
                    if not re.fullmatch(config["description"], value):
                        errors.append(
                            f"'{bag.path}': "
                            f"Description tag '{tag}' is present in "
                            "'bag-info.txt' but its value is not "
                            f"allowed: '{value}'."
                        )
        return not errors, errors

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

        path = kwargs["path"]

        # instantiate bag
        bag = bagit.Bag(str(path))

        bagit_profile = None
        if "profile_url" in kwargs:
            context.result.log.log(
                Context.INFO,
                body=f"""Loading profile from '{kwargs["profile_url"]}'.""",
            )
            context.set_progress("loading profile")
            context.push()
            bagit_profile = PatchedProfile(
                url=kwargs["profile_url"],
                profile=None,
                ignore_baginfo_tag_case=self.ignore_baginfo_tag_case,
            )
        else:
            # By default use the profile from the bag's bag-info
            if "BagIt-Profile-Identifier" in bag.info:
                # Attempt to load profile
                profile_url = bag.info["BagIt-Profile-Identifier"]
                context.result.log.log(
                    Context.INFO,
                    body=f"""Loading profile from '{profile_url}'.""",
                )
                context.set_progress("loading profile")
                context.push()
                try:
                    bagit_profile = PatchedProfile(
                        url=profile_url,
                        profile=None,
                        ignore_baginfo_tag_case=self.ignore_baginfo_tag_case,
                    )
                except SystemExit:
                    # `get_profile` method of `Profile` raises a sys.exit(1)
                    # if it cannot retrieve the profile
                    context.result.log.log(
                        Context.WARNING,
                        body=(
                            "Failed to retrieve the profile from the bag's "
                            f"bag-info from '{profile_url}'. "
                            "Using the default BagIt-profile from "
                            f"'{self.default_bagit_profile.url}'."
                        ),
                    )
                    context.push()
            else:
                context.result.log.log(
                    Context.INFO,
                    body=(
                        "Using the default BagIt-profile from "
                        f"'{self.default_bagit_profile.url}'."
                    ),
                )
                context.push()

        context.result.log.log(Context.INFO, body=f"'{path}': Validating bag.")
        context.set_progress(f"validating bag '{path}'")
        context.push()

        # check bag serialization
        valid_s11n, errors_s11n = self._validate_serialization(
            path=path,
            bagit_profile=(
                bagit_profile if bagit_profile else self.default_bagit_profile
            ),
        )

        # check bag against BagIt-profile
        valid_profile, errors_profile = self._validate_bagit_profile(
            bag=bag,
            bagit_profile=(
                bagit_profile if bagit_profile else self.default_bagit_profile
            )
        )
        if valid_profile is None:
            # execution failed
            context.result.success = False
            context.result.valid = None
            context.result.log.log(Context.ERROR, body=errors_profile)
            context.result.log.log(
                Context.INFO, body=f"'{path}': Bag validation failed."
            )
            context.set_progress("failure")
            context.push()
            return context.result

        # make additional checks of bag-info.txt
        valid_baginfo, errors_baginfo = self._validate_bag_info(
            bag=bag,
            bagit_profile=(
                bagit_profile if bagit_profile else self.default_bagit_profile
            )
        )

        # evaluate results
        if all([valid_s11n, valid_profile, valid_baginfo]):
            # bag valid
            context.result.valid = True
            context.result.log.log(
                Context.INFO, body=f"'{path}': Bag is valid."
            )
        else:
            # bag invalid
            context.result.valid = False
            context.result.log.log(
                Context.ERROR,
                body=errors_s11n + errors_profile + errors_baginfo,
            )
            context.result.log.log(
                Context.INFO, body=f"'{path}': Bag is invalid."
            )

        context.result.success = True
        context.set_progress("success")
        context.push()

        return context.result
