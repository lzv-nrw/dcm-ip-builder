"""
ValidationResult data-model definitions
"""

from typing import Optional
from dataclasses import dataclass, field

from dcm_common.models import DataModel

from dcm_object_validator.models import ValidationResult as _ValidationResult


@dataclass
class ValidationResult(_ValidationResult):
    logid: Optional[list[str]] = field(default_factory=list)

    @DataModel.serialization_handler("logid", "logId")
    @classmethod
    def logid_serialization(cls, value):
        """Performs `logid`-serialization."""
        if value is None:
            DataModel.skip()
        return value

    @DataModel.deserialization_handler("logid", "logId")
    @classmethod
    def logid_deserialization(cls, value):
        """Performs `logid`-deserialization."""
        if value is None:
            DataModel.skip()
        return value
