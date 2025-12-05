"""
ValidationConfig data-model definition
"""

from typing import Optional
from dataclasses import dataclass

from dcm_common.models import DataModel

from dcm_ip_builder.models.target import Target


@dataclass
class ValidationConfig(DataModel):
    """
    ValidationConfig `DataModel` used in the handler.

    Keyword arguments:
    target -- `Target`-object pointing to IE to be validated
    """

    target: Target
