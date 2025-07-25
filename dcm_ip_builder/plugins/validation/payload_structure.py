"""Payload Structure validation-plugin."""

from typing import TypedDict, Optional
import re
from pathlib import Path

from dcm_common.logger import LoggingContext as Context
from dcm_common.util import (
    NestedDict,
    get_profile,
    list_directory_content,
)

from .interface import (
    ValidationPlugin,
    ValidationPluginResult,
    ValidationPluginContext,
)


def load_baginfo(path) -> dict[str, str | list[str]]:
    result = {}
    if Path(path).is_file():
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if ":" not in line:
                continue
            field = tuple(
                map(lambda s: s.strip(), line.split(":", maxsplit=1))
            )
            if field[0] in result:
                result[field[0]] = [result[field[0]]]
            else:
                result[field[0]] = field[1]
    return result


# define types for typehinting of typed dictionaries
class RegexDict(TypedDict):
    regex: str


class PayloadFolderDict(TypedDict):
    string: str
    is_regex: bool


class PayloadStructurePlugin(ValidationPlugin):
    """
    Payload structure validation.

    The constructor expects a url or local path to a Payload-structure
    -profile. A validation on a directory can be performed by means
    of the get-method by supplying a path to the directory.

    Keyword arguments:
    default_profile_url -- file path or url to the desired
                           default BagIt-payload-profile.
    default_profile -- already instantiated BagIt-payload-profile as dictionary
                       (default None)
    """

    _NAME = "payload-structure"
    _DISPLAY_NAME = "Payload-Structure-Validation-Plugin"
    _DESCRIPTION = "Payload structure validation."

    def __init__(
        self,
        default_profile_url: str,
        default_profile: Optional[NestedDict] = None,
        **kwargs,
    ) -> None:

        super().__init__(**kwargs)

        self.default_profile_url = default_profile_url

        self.default_profile: NestedDict
        if isinstance(default_profile, dict):
            self.default_profile = default_profile
        else:
            self.default_profile = get_profile(self.default_profile_url)

    @classmethod
    def _get_allowed_folders(
        cls, profile: NestedDict
    ) -> list[PayloadFolderDict]:

        # read up on some information from profile content
        # used to handle the varying types of values under the common key
        # 'Payload-Folders-Allowed'
        def process_allowed_regex_from_profile(
            input_value: str | RegexDict,
        ) -> PayloadFolderDict:
            """
            Returns a dict with the two keys 'string' and 'is_regex' to
            consistently process allowed and required directories in
            payload profile.

            Keyword arguments:
            input_value -- input as read from json; either string literal or
                        dict containing the key 'regex'
            """

            if isinstance(input_value, dict):
                return {
                    "string": input_value["regex"]
                    + ("/" if input_value["regex"][-1] != "/" else ""),
                    "is_regex": True,
                }

            return {
                "string": input_value
                + ("/" if input_value[-1] != "/" else ""),
                "is_regex": False,
            }

        if "Payload-Folders-Allowed" in profile:
            return [
                process_allowed_regex_from_profile(x)
                for x in profile["Payload-Folders-Allowed"]
            ]
        return [{"string": r".*", "is_regex": True}]

    @classmethod
    def _get_required_folders(
        cls, profile: NestedDict
    ) -> list[PayloadFolderDict]:
        if "Payload-Folders-Required" in profile:
            return [
                {"string": x, "is_regex": False}
                for x in profile["Payload-Folders-Required"]
            ]
        return []

    @classmethod
    def _validate_more(cls, kwargs):
        # ensure path is a directory
        if not Path(kwargs["path"]).is_dir():
            return False, "'path' has to be a directory"
        # ensure profile can be instantiated
        if "profile_url" in kwargs:
            try:
                get_profile(kwargs["profile_url"])
            except Exception as exc:  # pylint: disable=broad-except
                # execution failed
                return (
                    False,
                    "Cannot instantiate BagIt-payload-profile. An exception "
                    + f"of type '{type(exc).__name__}' occurred: {exc}.",
                )
        return super()._validate_more(kwargs)

    def match_any_regex(
        self,
        path: str,
        patterns: list[PayloadFolderDict],
        use_as_regex_anyway: bool = False,
    ) -> bool:
        """
        Returns True if any entry from patterns (dict with boolean
        'is_regex' and str 'string') fully matches with the provided
        path.

        Keyword arguments:
        path -- path to match as string
        patterns -- list of dicts each with the two keys 'is_regex'
                    (boolean) and 'string' (str).
        use_as_regex_anyway -- boolean to determine whether the patterns
                               are checked for 'is_regex' key
                               (default False)
        """

        path = Path(path).as_posix()
        for pattern in patterns:
            if use_as_regex_anyway or pattern["is_regex"]:
                match = re.match(pattern["string"], path)
                if match:
                    return True
            else:
                if Path(pattern["string"]).as_posix() == path:
                    return True
        return False

    def _validate_payload_directories_allowed(
        self, profile: NestedDict
    ) -> tuple[bool, list[str]]:
        """
        Validate the ``Payload-Folders-Allowed`` tag by checking for
        required_but_not_allowed-directories.
        """

        payload_directories_validate = True
        errors = []

        # for each member of required, ensure it is also in allowed
        required_but_not_allowed = [
            f
            for f in self._get_required_folders(profile)
            if not self.match_any_regex(
                f["string"], self._get_allowed_folders(profile)
            )
        ]
        if required_but_not_allowed:
            payload_directories_validate = False
            for file in required_but_not_allowed:
                required_but_not_allowed_path = file["string"]
                errors.append(
                    "Required payload directory "
                    f"'{required_but_not_allowed_path}' not listed in "
                    "Payload-Folders-Allowed."
                )

        return payload_directories_validate, errors

    def _validate_payload_directories_required(
        self, path: Path, profile: NestedDict
    ) -> tuple[bool, list[str]]:
        """
        Validate the ``Payload-Folders-Required`` tag.

        This validation step checks whether all required directories
        actually exist.

        Keyword arguments:
        path -- path to the directory to be validated
        profile -- profile against which to validate directory
        """

        payload_directories_validate = True
        errors = []

        # Payload-directory structure is optional for now
        if "Payload-Folders-Required" in profile:
            for payload_dir in profile["Payload-Folders-Required"]:
                if not (path / "data" / payload_dir).is_dir():
                    payload_directories_validate = False
                    errors.append(
                        f"Required payload directory '{payload_dir}' "
                        "is not present."
                    )

        return payload_directories_validate, errors

    def _validate_payload_dir_files(
        self, path: Path, profile: NestedDict
    ) -> tuple[bool, list[str]]:
        """
        Validate that files are only located in directories allowed by
        the payload profile. All relative file paths have to fully match
        their prefix with Payload-Folders-Allowed.

        Keyword arguments:
        path -- path to the directory to be validated
        profile -- profile against which to validate directory
        """

        payload_files_validate = True
        errors = []

        # Payload-directory structure is optional for now
        if "Payload-Folders-Allowed" in profile:
            # list all files in payload that are allowed
            disallowed_payload_files = list_directory_content(
                path / "data",
                pattern="**/*",
                condition_function=lambda p: (
                    p.is_file()
                    and not self.match_any_regex(
                        str(p.relative_to(path / "data")),
                        self._get_allowed_folders(profile),
                        use_as_regex_anyway=True,
                    )
                ),
            )
            # invalid if list is non-empty, list bad files in log
            if disallowed_payload_files:
                payload_files_validate = False
                for file in disallowed_payload_files:
                    relfile = file.relative_to(path)
                    errors.append(
                        f"File '{relfile}' found in illegal location "
                        "of payload directory."
                    )

        return payload_files_validate, errors

    def _validate_payload_files_capitalization(
        self, path: Path
    ) -> tuple[bool, list[str]]:
        """
        Validate that files in the payload directory do not differ by
        only their capitalization.

        Keyword arguments:
        path -- path to the directory to be validated
        """

        payload_file_capitalization_validates = True
        errors = []

        # list files in payload dir
        payload_files = list_directory_content(
            path / "data",
            pattern="**/*",
            condition_function=lambda p: (p.is_file()),
        )

        # iterate files and check for multiple occurrences for
        # filename.lower()
        checked: dict[str, str] = {}
        for file in payload_files:
            file_relative = file.relative_to(path)
            file_lower = str(file_relative).lower()
            if file_lower in checked:
                payload_file_capitalization_validates = False
                errors.append(
                    f"File '{file_relative}' and '{checked[file_lower]}' "
                    "only differ in their capitalization."
                )
            else:
                checked[file_lower] = str(file_relative)

        return payload_file_capitalization_validates, errors

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

        profile = None
        if "profile_url" in kwargs:
            context.result.log.log(
                Context.INFO,
                body=f"""Loading profile from '{kwargs["profile_url"]}'.""",
            )
            context.set_progress("loading profile")
            context.push()
            profile = get_profile(kwargs["profile_url"])
        else:
            # Read the bag-info.txt
            bag_info_dict = load_baginfo(path / "bag-info.txt")
            if "BagIt-Payload-Profile-Identifier" in bag_info_dict:
                # By default use the profile from the bag's bag-info
                profile_url = bag_info_dict["BagIt-Payload-Profile-Identifier"]
                context.result.log.log(
                    Context.INFO,
                    body=f"""Loading profile from '{profile_url}'.""",
                )
                context.set_progress("loading profile")
                context.push()
                # Attempt to load profile
                try:
                    profile = get_profile(profile_url)
                except Exception as e:  # pylint: disable=broad-except
                    fail_msg = (
                        "Failed to retrieve the profile from the bag's "
                        f"bag-info from '{profile_url}': {str(e)}"
                    )
                    context.result.log.log(
                        Context.WARNING,
                        body=(
                            fail_msg + " Using the default "
                            "BagIt-payload-profile from "
                            f"'{self.default_profile_url}'."
                        ),
                    )
                    context.push()
            else:
                context.result.log.log(
                    Context.INFO,
                    body=(
                        "Using the default BagIt-payload-profile from "
                        f"'{self.default_profile_url}'."
                    )
                )
                context.push()

        context.result.log.log(
            Context.INFO, body=f"Validating directory '{path}'."
        )
        context.set_progress(f"validating directory '{path}'")
        context.push()

        # perform validation
        valid_dir_allowed, errors_dir_allowed = (
            self._validate_payload_directories_allowed(
                profile=profile if profile else self.default_profile
            )
        )
        valid_dir_required, errors_dir_required = (
            self._validate_payload_directories_required(
                path=path, profile=profile if profile else self.default_profile
            )
        )
        valid_files, errors_files = self._validate_payload_dir_files(
            path=path, profile=profile if profile else self.default_profile
        )
        valid_files_cap, errors_files_cap = (
            self._validate_payload_files_capitalization(path=path)
        )

        # evaluate results
        if all(
            [
                valid_dir_allowed,
                valid_dir_required,
                valid_files,
                valid_files_cap,
            ]
        ):
            # directory valid
            context.result.valid = True
            context.result.log.log(
                Context.INFO, body=f"Directory '{path}' is valid."
            )
        else:
            # directory invalid
            context.result.valid = False
            context.result.log.log(
                Context.ERROR,
                body=errors_dir_allowed
                + errors_dir_required
                + errors_files
                + errors_files_cap,
            )
            context.result.log.log(
                Context.INFO, body=f"Directory '{path}' is invalid."
            )

        context.result.success = True
        context.set_progress("success")
        context.push()

        return context.result
