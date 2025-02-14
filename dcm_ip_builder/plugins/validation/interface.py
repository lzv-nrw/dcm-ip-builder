"""Validation-plugin-interface."""

from typing import Optional
from dataclasses import dataclass, field
import abc

from dcm_common.plugins import (
    PluginInterface,
    PluginResult,
    PluginExecutionContext,
    Signature,
    Argument,
    JSONType,
)


@dataclass
class ValidationPluginResult(PluginResult):
    """
    Data model for the result of `ValidationPlugin`-invocations.
    """

    success: Optional[bool] = None
    valid: Optional[bool] = None


@dataclass
class ValidationPluginContext(PluginExecutionContext):
    """
    Data model for the execution context of `ValidationPlugin`-invocations.
    """

    result: ValidationPluginResult = field(
        default_factory=ValidationPluginResult
    )


class ValidationPlugin(PluginInterface, metaclass=abc.ABCMeta):
    """
    Validation plugin-base class.

    The plugin-context and result are already being set here.
    """

    _CONTEXT = "validation"
    _SIGNATURE = Signature(
        path=Argument(
            type_=JSONType.STRING,
            required=True,
            description="target path for validation",
            example="relative/path/to/directory",
        ),
        profile_url=Argument(
            type_=JSONType.STRING,
            required=False,
            description="file path or url to the desired BagIt-profile",
            example="bagit_profiles/dcm_bagit_profile_v1.0.0.json",
        ),
    )
    _RESULT_TYPE = ValidationPluginResult

    @abc.abstractmethod
    def _get(
        self, context: ValidationPluginContext, /, **kwargs
    ) -> ValidationPluginResult:
        raise NotImplementedError(
            f"Class '{self.__class__.__name__}' does not define method 'get'."
        )

    def get(  # this simply narrows down the involved types
        self, context: Optional[ValidationPluginContext], /, **kwargs
    ) -> ValidationPluginResult:
        return super().get(context, **kwargs)
