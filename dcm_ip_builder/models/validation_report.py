"""
ValidationReport data-model definition
"""

from dataclasses import dataclass, field

from dcm_common.models import Report as BaseReport

from dcm_ip_builder.models.validation_result import ValidationResult


@dataclass
class ValidationReport(BaseReport):
    data: ValidationResult = field(default_factory=ValidationResult)
