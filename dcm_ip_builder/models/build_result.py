"""
BuildResult data-model definition
"""

from typing import Optional
from pathlib import Path
from dataclasses import dataclass, field

from dcm_common.models import DataModel


@dataclass
class BuildResult(DataModel):
    """
    Build result `DataModel`

    Keyword arguments:
    path -- path to output directory relative to shared file system
    valid -- overall validity; `True` if valid
    logid -- list of ids for related reports
    """

    path: Optional[Path] = None
    valid: Optional[bool] = None
    logid: list[str] = field(default_factory=list)

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

    @DataModel.serialization_handler("logid", "logId")
    @classmethod
    def logid_serialization(cls, value):
        """Performs `logid`-serialization."""
        return value

    @DataModel.deserialization_handler("logid", "logId")
    @classmethod
    def logid_deserialization(cls, value):
        """Performs `logid`-deserialization."""
        return value
