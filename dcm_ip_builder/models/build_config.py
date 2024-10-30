"""
BuildConfig data-model definition
"""

from typing import Optional
from dataclasses import dataclass

from dcm_common.models import DataModel

from dcm_ip_builder.models.target import Target


@dataclass
class _BuildConfig(DataModel):
    """
    _BuildConfig `DataModel` used in the handler.

    Keyword arguments:
    target -- `Target`-object pointing to IE to be built
    config -- a base64-encoded string of a serialized class
              or a url pointing to a python module
              with the configuration for metadata mapper and converter
    bagit_profile_url -- url pointing to BagIt-Profile
                         (default None)
    payload_profile_url -- url pointing to BagIt-Payload-Profile
                           (default None)
    """

    target: Target
    config: str
    bagit_profile_url: Optional[str] = None
    payload_profile_url: Optional[str] = None


@dataclass
class BuildConfig(DataModel):
    """
    BuildConfig `DataModel`

    Keyword arguments:
    target -- `Target`-object pointing to IE to be built
    config -- class-object with properties `CONVERTER` and
              `MAPPER`
    bagit_profile_url -- url pointing to BagIt-Profile
                         (default None)
    payload_profile_url -- url pointing to BagIt-Payload-Profile
                           (default None)
    """

    target: Target
    config: type
    bagit_profile_url: Optional[str] = None
    payload_profile_url: Optional[str] = None

    @property
    def converter(self) -> type:
        "Returns `CONVERTER` from `config`."
        return self.config.CONVERTER

    @property
    def mapper(self) -> type:
        "Returns `MAPPER` from `config`."
        return self.config.MAPPER

    @DataModel.serialization_handler("config")
    @classmethod
    def config_serialization_handler(cls, value):
        """Skip `config`-serialization."""
        DataModel.skip()

    @DataModel.deserialization_handler("config")
    @classmethod
    def config_deserialization(cls, value):
        """Skip `config`-deserialization."""
        DataModel.skip()
