"""
BuildConfig data-model definition
"""

from typing import Optional
from dataclasses import dataclass

from dcm_common.models import DataModel
from dcm_common.services.plugins import PluginConfig

from dcm_ip_builder.models.target import Target


@dataclass
class BuildConfig(DataModel):
    """
    BuildConfig `DataModel`

    Keyword arguments:
    target -- `Target`-object pointing to IE to be built
    mapping_plugin -- mapping-plugin configuration
    validate -- whether to run validation after build
                (default True)
    bagit_profile_url -- url pointing to BagIt-Profile
                         (default None)
    payload_profile_url -- url pointing to BagIt-Payload-Profile
                           (default None)
    """

    target: Target
    mapping_plugin: PluginConfig
    validate: bool = True
    bagit_profile_url: Optional[str] = None
    payload_profile_url: Optional[str] = None
