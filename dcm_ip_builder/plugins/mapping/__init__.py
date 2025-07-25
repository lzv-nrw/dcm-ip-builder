from .interface import MappingPlugin, MappingPluginResult
from .generic import (
    GenericMapper,
    GenericB64Plugin,
    GenericUrlPlugin,
    GenericStringPlugin,
)
from .demo import DemoMappingPlugin
from .xslt import XSLTMappingPlugin


__all__ = [
    "MappingPlugin",
    "MappingPluginResult",
    "GenericMapper",
    "GenericB64Plugin",
    "GenericUrlPlugin",
    "GenericStringPlugin",
    "DemoMappingPlugin",
    "XSLTMappingPlugin",
]
