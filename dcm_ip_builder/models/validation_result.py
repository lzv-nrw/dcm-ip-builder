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
    origin_system_id -- identifier of the origin system
    external_id -- identifier of the record in the external system
    details -- detailed validation results by plugin
    """

    success: Optional[bool] = None
    valid: Optional[bool] = None
    origin_system_id: Optional[str] = None
    external_id: Optional[str] = None
    details: dict[str, ValidationPluginResult] = field(default_factory=dict)

    # This is a special attribute that is only used to discern JobData-models.
    # It is only needed by the sdk to determine the correct model during
    # deserialization. It does not need to be set manually, the handlers take
    # care of everything.
    # The leading underscore makes the DataModel-(de-)serializer ignore it by
    # default. In order to still include it in API-responses, a custom
    # serialization-handler is defined below
    _request_type: Optional[str] = None

    @DataModel.serialization_handler("origin_system_id", "originSystemId")
    @classmethod
    def origin_system_id_serialization_handler(cls, value):
        """Performs `origin_system_id`-serialization."""
        if value is None:
            DataModel.skip()
        return value

    @DataModel.deserialization_handler("origin_system_id", "originSystemId")
    @classmethod
    def origin_system_id_deserialization(cls, value):
        """Performs `origin_system_id`-deserialization."""
        if value is None:
            DataModel.skip()
        return value

    @DataModel.serialization_handler("external_id", "externalId")
    @classmethod
    def external_id_serialization_handler(cls, value):
        """Performs `external_id`-serialization."""
        if value is None:
            DataModel.skip()
        return value

    @DataModel.deserialization_handler("external_id", "externalId")
    @classmethod
    def external_id_deserialization(cls, value):
        """Performs `external_id`-deserialization."""
        if value is None:
            DataModel.skip()
        return value

    @DataModel.serialization_handler("_request_type", "requestType")
    @classmethod
    def _request_type_serialization_handler(cls, _):
        """
        Performs `_request_type`-serialization.

        Always generate the constant value for this JobData-type.
        """
        return "validation"
