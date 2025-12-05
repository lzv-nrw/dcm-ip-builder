"""Custom BagItProfileValidator-class definition."""

from typing import Mapping, Optional
from pathlib import Path

import bagit_utils


class BagItProfileValidator(bagit_utils.BagItProfileValidator):

    _ACCEPTED_SERIALIZATION_VALUES = ["forbidden"]

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

    @classmethod
    def validate_accept_serialization(cls, profile: Mapping) -> None:
        super().validate_accept_serialization(profile)
        if (
            "Accept-Serialization" in profile
            and len(profile["Accept-Serialization"]) != 0
        ):
            raise ValueError(
                "This service does not support validation of "
                + "serialized BagIt-Bags."
            )

    @classmethod
    def validate_accept_bagit_version(cls, profile: Mapping) -> None:
        super().validate_accept_bagit_version(profile)
        if (
            "Accept-BagIt-Version" in profile
            and "1.0" not in profile["Accept-BagIt-Version"]
        ):
            raise ValueError(
                "This service only supports validation with "
                + "BagIt version '1.0'."
            )
