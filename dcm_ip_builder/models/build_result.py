"""
BuildResult data-model definition
"""

from typing import Optional
from pathlib import Path
from dataclasses import dataclass

from dcm_common.models import DataModel

from .validation_result import ValidationResult


@dataclass
class BuildResult(ValidationResult):
    """
    Build result `DataModel`

    Keyword arguments:
    <all args from ValidationResult-model>
    path -- path to output directory relative to shared file system
    """

    path: Optional[Path] = None

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

    @DataModel.serialization_handler("_request_type", "requestType")
    @classmethod
    def _request_type_serialization_handler(cls, _):
        """
        Performs `_request_type`-serialization.

        Always generate the constant value for this JobData-type.
        (See base model ValidationResult for details)
        """
        return "build"
