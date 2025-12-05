"""Utility definitions."""

import sys
from typing import Optional
from json import loads, JSONDecodeError
from pathlib import Path

from dcm_common.util import NestedDict, list_directory_content

from dcm_ip_builder.components import BagItProfileValidator


def _print_and_raise_error(msg: str, exc_info: ValueError = None):
    print(
        "\033[1;31m"
        + f"{msg}"
        + "\033[0m",
        file=sys.stderr,
    )
    if exc_info:
        raise ValueError(msg) from exc_info
    raise ValueError(msg)


def load_profile(
    profile: Optional[NestedDict] = None, path: Optional[Path] = None,
) -> dict[str, NestedDict]:
    """
    Loads and validates profile from the given dictionary or path.
    """
    try:
        if profile is not None:
            profile = BagItProfileValidator.load_profile(profile=profile)
        else:
            profile = BagItProfileValidator.load_profile(profile_src=path)
    except ValueError as exc_info:
        _print_and_raise_error(
            f"Failed to load profile from '{profile if profile else path}': "
            + f"{str(exc_info)}",
            exc_info,
        )
    if "BagIt-Profile-Info" not in profile:
        _print_and_raise_error(
            f"Failed to load profile from '{profile if profile else path}': "
            + "profile does not define the required section "
            + "'BagIt-Profile-Info'."
        )
    if "BagIt-Profile-Identifier" not in profile["BagIt-Profile-Info"]:
        _print_and_raise_error(
            f"Failed to load profile from '{profile if profile else path}': "
            + "profile does not define the required field "
            + "'BagIt-Profile-Identifier' in the section "
            + "'BagIt-Profile-Info'."
        )
    return profile


def load_profiles_from_string(json: str) -> dict[str, NestedDict]:
    """Loads profiles from the given JSON-string."""

    try:
        profiles_json = loads(json)
    except JSONDecodeError as exc_info:
        _print_and_raise_error(
            f"Invalid profile configuration: {exc_info}.",
            exc_info
        )

    if not isinstance(profiles_json, list):
        _print_and_raise_error(
            "Invalid profile configuration: Expected list of profile "
            + f"configurations but got '{type(profiles_json).__name__}'."
        )

    profiles = {}
    for p in profiles_json:
        try:
            profile = load_profile(profile=p)
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            print(
                "\033[1;33m"
                "WARNING: Skipping loading profile: "
                + f"{exc_info}"
                + "\033[0m",
                file=sys.stderr,
            )
            continue
        uri = profile["BagIt-Profile-Info"]["BagIt-Profile-Identifier"]
        if uri in profiles:
            _print_and_raise_error(
                f"Non-unique uri in the profile configuration '{uri}'."
            )
        profiles[uri] = profile

    return profiles


def load_profiles_from_dir(path: Path) -> dict[str, NestedDict]:
    """Loads profiles from JSON-files in the given `path`."""
    profiles = {}
    for p in list_directory_content(
        path, pattern="**/*", condition_function=lambda p: p.is_file()
    ):
        try:
            profile = load_profile(path=p)
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            print(
                "\033[1;33m"
                "WARNING: Skipping loading profile from invalid file: "
                + f"{exc_info}"
                + "\033[0m",
                file=sys.stderr,
            )
            continue
        uri = profile["BagIt-Profile-Info"]["BagIt-Profile-Identifier"]
        if uri in profiles:
            _print_and_raise_error(
                f"Non-unique uri in the profile configuration '{uri}'."
            )
        profiles[uri] = profile

    return profiles
