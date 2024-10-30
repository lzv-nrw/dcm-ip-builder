"""
Target data-model definition
"""

from dataclasses import dataclass, field
from pathlib import Path

from dcm_common.models import DataModel

from dcm_ip_builder.models.validation_result import ValidationResult
from dcm_ip_builder.models.build_result import BuildResult


@dataclass
class Target(DataModel):
    """
    Target `DataModel`

    Keyword arguments:
    path -- path to target directory relative to `FS_MOUNT_POINT`
    validation -- `ValidationResult` associated with `self`
    build -- `BuildResult` associated with `self`
    """

    path: Path
    build: BuildResult = field(default_factory=BuildResult)
    validation: ValidationResult = field(default_factory=ValidationResult)

    @DataModel.serialization_handler("path")
    @classmethod
    def path_serialization(cls, value):
        """Performs `path`-serialization."""
        return str(value)

    @DataModel.deserialization_handler("path")
    @classmethod
    def path_deserialization(cls, value):
        """Performs `path`-deserialization."""
        return Path(value)
