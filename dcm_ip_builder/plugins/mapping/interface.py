"""Metadata mapping-plugin-interface."""

from typing import Optional
from dataclasses import dataclass, field
import abc

from dcm_common.models import DataModel
from dcm_common.plugins import (
    PluginInterface,
    PluginResult,
    PluginExecutionContext,
    Signature,
    Argument,
    JSONType,
)


@dataclass
class MappingPluginResult(PluginResult):
    """
    Data model for the result of `MappingPlugin`-invocations.
    """

    metadata: Optional[dict[str, str | list[str]]] = None
    success: Optional[bool] = None

    @DataModel.serialization_handler("metadata")
    @classmethod
    def metadata_serialization(cls, value):
        """Performs `metadata`-serialization."""
        if value is None:
            DataModel.skip()
        return value

    @DataModel.deserialization_handler("metadata")
    @classmethod
    def metadata_deserialization(cls, value):
        """Performs `metadata`-deserialization."""
        if value is None:
            DataModel.skip()
        return value


@dataclass
class MappingPluginContext(PluginExecutionContext):
    """
    Data model for the execution context of `MappingPlugin`-invocations.
    """

    result: MappingPluginResult = field(
        default_factory=MappingPluginResult
    )


class MappingPlugin(PluginInterface, metaclass=abc.ABCMeta):
    """
    Metadata mapping plugin-base class.

    An implementation of this interface should only ever extend the
    default `_SIGNATURE`.

    The plugin-context is already being set here.

    An implementation's `PluginResult` should inherit from
    `MappingPluginResult`.
    """

    _CONTEXT = "mapping"
    _SIGNATURE = Signature(
        # this is intentionally left as arbitrary regarding file or dir
        # to allow maximum flexibility when using the interface
        path=Argument(
            type_=JSONType.STRING,
            required=False,
            description=(
                "path to source metadata to be mapped; filled automatically"
            ),
            example="relative/path/to/file.xml",
        )
    )
    _RESULT_TYPE = MappingPluginResult

    @abc.abstractmethod
    def _get(
        self, context: MappingPluginContext, /, **kwargs
    ) -> MappingPluginResult:
        raise NotImplementedError(
            f"Class '{self.__class__.__name__}' does not define method 'get'."
        )

    def get(  # this simply narrows down the involved types
        self, context: Optional[MappingPluginContext], /, **kwargs
    ) -> MappingPluginResult:
        return super().get(context, **kwargs)
