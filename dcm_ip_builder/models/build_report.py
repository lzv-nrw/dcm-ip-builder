"""
BuildReport data-model definition
"""

from typing import Optional
from dataclasses import dataclass, field

from dcm_common.models import JSONObject, DataModel, Report as BaseReport

from dcm_ip_builder.models.build_result import BuildResult


@dataclass
class BuildReport(BaseReport):
    data: BuildResult = field(default_factory=BuildResult)
    children: Optional[dict[str, BaseReport | JSONObject]] = None

    @DataModel.serialization_handler("children")
    @classmethod
    def children_serialization(cls, value):
        """Performs `children`-serialization."""
        if value is None:
            DataModel.skip()
        return {
            c: (r.json if isinstance(r, BaseReport) else r)
            for c, r in value.items()
        }

    @DataModel.deserialization_handler("children")
    @classmethod
    def children_deserialization(cls, value):
        """Performs `children`-deserialization."""
        if value is None:
            DataModel.skip()
        return value
