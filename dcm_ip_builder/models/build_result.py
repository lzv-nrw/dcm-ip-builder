"""
BuildResult data-model definition
"""

from typing import Optional
from pathlib import Path
from dataclasses import dataclass, field

from dcm_common.models import DataModel
from dcm_common.plugins import PluginResult


@dataclass
class BuildResult(DataModel):
    """
    Build result `DataModel`

    Keyword arguments:
    build -- property to differentiate the job results.
             Only uses default value to allow model validation in the sdk.
    success -- overall success of build process
    path -- path to output directory relative to shared file system
    valid -- overall validity; true if IP is valid
    details -- detailed results by plugin
    """

    build_plugin: str = field(default_factory=lambda: "build_plugin")
    success: Optional[bool] = None
    path: Optional[Path] = None
    valid: Optional[bool] = None
    details: dict[str, PluginResult] = field(default_factory=dict)

    @DataModel.serialization_handler("path")
    @classmethod
    def path_serialization_handler(cls, value):
        """Performs `path`-serialization."""
        if value is None:
            DataModel.skip()
        return str(value)

    @DataModel.deserialization_handler("path")
    @classmethod
    def path_deserialization(cls, value):
        """Performs `path`-deserialization."""
        if value is None:
            DataModel.skip()
        return Path(value)
