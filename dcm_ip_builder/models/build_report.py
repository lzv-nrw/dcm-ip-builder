"""
BuildReport data-model definition
"""

from dataclasses import dataclass, field

from dcm_ip_builder.models.build_result import BuildResult
from dcm_ip_builder.models.validation_report import ValidationReport


@dataclass
class BuildReport(ValidationReport):
    data: BuildResult = field(default_factory=BuildResult)
