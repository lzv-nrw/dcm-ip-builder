"""Definition of the generic-mapper plugins."""

from typing import Any
from pathlib import Path
import base64
from urllib import request
import importlib
import abc

from dcm_common import LoggingContext as Context
from dcm_common.plugins import PythonDependency, Signature, Argument, JSONType

from .interface import MappingPlugin, MappingPluginContext


class GenericMapper(metaclass=abc.ABCMeta):
    """Interface for a generic metadata mapper."""

    @classmethod
    def __subclasshook__(cls, subclass):
        return (
            hasattr(subclass, "get_metadata")
            and callable(subclass.get_metadata)
            or NotImplemented
        )

    @abc.abstractmethod
    def get_metadata(
        self, path: Path, /, **kwargs
    ) -> dict[str, str | list[str]]:
        """
        Returns the mapped metadata as a dictionary of strings and lists
        of string.

        Keyword arguments:
        path -- path to source metadata
        kwargs -- all kwargs passed to the plugin in mapper.args
        """

        raise NotImplementedError(
            f"Class {self.__class__.__name__} does not define method "
            + "'get_metadata'."
        )


class GenericMappingPlugin(MappingPlugin, metaclass=abc.ABCMeta):
    """
    Interface for generic metadata mapping-plugins.
    """

    _DISPLAY_NAME = "Generic-Mapper-Plugin"
    _NAME = "generic-mapper-plugin-"

    @property
    @abc.abstractmethod
    def _TYPE(self) -> str:
        """
        'GenericMapper'-source type identifier like 'base64' (used in
        logs and to determine argument in signature where mapper is
        referenced).
        """
        raise NotImplementedError(
            f"Class '{self.__class__.__name__}' does not define property "
            + "'_TYPE'."
        )

    @abc.abstractmethod
    def _load_mapper(self, src: str) -> tuple[bool, str, Any]:
        """
        Loads `GenericMapper`-class. Returns a tuple of success,
        message, and (if successful) alleged (not yet validated) mapper-
        class.
        """
        raise NotImplementedError(
            f"Class '{self.__class__.__name__}' does not define method "
            + "'_load_mapper'."
        )

    def _validate_mapper(self, mapper: Any) -> tuple[bool, str]:
        """Validates 'GenericMapper'-implementation."""
        if not issubclass(mapper, GenericMapper):
            return (
                False,
                "mapper does not implement 'GenericMapper'-interface",
            )
        return True, ""

    def _get(self, context: MappingPluginContext, /, **kwargs):
        # decode/deserialize and validate here since this is actual work
        # and should not be done by app (i.e. in an input-handler)
        context.set_progress(f"loading generic mapper from {self._TYPE}")
        context.push()
        mapper_ok, msg, mapper = self._load_mapper(
            kwargs["mapper"][self._TYPE]
        )
        if not mapper_ok:
            context.result.success = False
            context.result.log.log(
                Context.ERROR, body=f"Unable to load mapper: {msg}"
            )
            context.set_progress("failure")
            context.push()
            return context.result
        mapper_ok, msg = self._validate_mapper(mapper)
        if not mapper_ok:
            context.result.success = False
            context.result.log.log(Context.ERROR, body=msg)
            context.set_progress("failure")
            context.push()
            return context.result

        context.result.log.log(
            Context.INFO, body=f"Mapping metadata of '{kwargs['path']}'."
        )
        context.set_progress(f"mapping metadata of '{kwargs['path']}'")
        context.push()

        # run mapper
        try:
            context.result.metadata = mapper().get_metadata(
                Path(kwargs["path"]), **kwargs["mapper"]["args"]
            )
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            context.result.success = False
            context.result.log.log(
                Context.ERROR,
                body=(
                    "Provided 'GenericMapper' encountered an error: "
                    + str(exc_info)
                ),
            )
            context.set_progress("failure")
            context.push()
            return context.result

        # TODO: validate type/serializability of metadata?
        context.result.success = True
        context.set_progress("success")
        context.push()
        return context.result


class GenericB64Plugin(GenericMappingPlugin):
    """
    Metadata mapping-plugin that works based on base64-encoded
    implementations of the `GenericMapper`-interface.
    """

    _TYPE = "base64"
    _NAME = GenericMappingPlugin.name + _TYPE
    _DESCRIPTION = (
        "Generic metadata mapping based on base64-encoded implementations of "
        + "the 'GenericMapper'-interface."
    )
    _SIGNATURE = Signature(
        path=MappingPlugin.signature.properties["path"],
        mapper=Argument(
            type_=JSONType.OBJECT,
            required=True,
            description="mapper details",
            properties={
                _TYPE: Argument(
                    type_=JSONType.STRING,
                    required=True,
                    description=(
                        "'GenericMapper'-implementation as base64-encoded "
                        + "string"
                    ),
                ),
                "args": Argument(
                    type_=JSONType.OBJECT,
                    required=True,
                    description=(
                        "additional arguments passed to the "
                        + "'GenericMapper.get_metadata'-method"
                    ),
                    additional_properties=True,
                ),
            },
        ),
    )
    _DEPENDENCIES = [PythonDependency("dill")]

    @classmethod
    def requirements_met(cls) -> tuple[bool, str]:
        try:
            # pylint: disable=import-outside-toplevel, unused-import
            import dill
        except ImportError as exc_info:
            return False, f"Unable to load dill: {exc_info}"
        return True, "ok"

    def __init__(self, **kwargs) -> None:
        # pylint: disable=import-outside-toplevel
        import dill

        self._dill = dill
        super().__init__(**kwargs)

    def _load_mapper(self, src: str) -> tuple[bool, str, Any]:
        """Loads `GenericMapper`-class."""
        try:
            # decode the mapper
            decoded_mapper = base64.b64decode(src)
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            return (False, f"error decoding mapper: {exc_info}", None)
        try:
            # de-serialize the mapper object
            return True, "ok", self._dill.loads(decoded_mapper)
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            return (False, f"error deserializing mapper: {exc_info}", None)


class GenericUrlPlugin(GenericMappingPlugin):
    """
    Metadata mapping-plugin that works based on implementations of the
    `GenericMapper`-interface provided via url.
    """

    _TYPE = "url"
    _NAME = GenericMappingPlugin.name + _TYPE
    _DESCRIPTION = (
        "Generic metadata mapping based on implementations of the "
        + "'GenericMapper'-interface provided via url."
    )
    _SIGNATURE = Signature(
        path=MappingPlugin.signature.properties["path"],
        mapper=Argument(
            type_=JSONType.OBJECT,
            required=True,
            description="mapper details",
            properties={
                _TYPE: Argument(
                    type_=JSONType.STRING,
                    required=True,
                    description=("'GenericMapper'-implementation url"),
                ),
                "args": Argument(
                    type_=JSONType.OBJECT,
                    required=True,
                    description=(
                        "additional arguments passed to the "
                        + "'GenericMapper.get_metadata'-method"
                    ),
                    additional_properties=True,
                ),
            },
        ),
    )

    def _load_mapper(self, src: str) -> tuple[bool, str, Any]:
        """Loads `GenericMapper`-class."""
        # read data from source url
        try:
            with request.urlopen(src, timeout=10) as remote_file:
                url_src = remote_file.read()
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            return False, f"cannot access url '{src}': {exc_info}", None

        # create spec and module, then run code
        try:
            # create spec and generate module
            spec = importlib.util.spec_from_loader(
                name=f"external_mapper-{src}", loader=None, origin=src
            )
            module = importlib.util.module_from_spec(spec)
            # run
            # pylint: disable-next=exec-used
            exec(url_src, module.__dict__)
        # pylint: disable=broad-exception-caught
        except Exception as exc_info:
            return False, f"cannot interpret source: {exc_info}", None

        # search for expected GenericMapper (named ExternalMapper)
        if hasattr(module, "ExternalMapper"):
            return True, "", module.ExternalMapper
        return (
            False,
            f"cannot find class-spec for 'ExternalMapper' in {src}",
            None,
        )
