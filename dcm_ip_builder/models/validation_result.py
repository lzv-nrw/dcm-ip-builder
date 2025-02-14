"""
ValidationResult data-model definitions
"""

from typing import Optional
from dataclasses import dataclass, field

from dcm_common.models import DataModel

from dcm_ip_builder.plugins.validation import ValidationPluginResult


@dataclass
class ValidationResult(DataModel):
    """
    Validation result `DataModel`

    Keyword arguments:
    success -- overall success of build process
    valid -- overall validity; true if IP is valid
    details -- detailed validation results by plugin
    """

    success: Optional[bool] = None
    valid: Optional[bool] = None
    details: dict[str, ValidationPluginResult] = field(default_factory=dict)
