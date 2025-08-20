"""Input handlers for the 'DCM IP Builder'-app."""

from typing import Mapping
from pathlib import Path

from data_plumber_http import Property, Object, Url, Boolean
from dcm_common.services.handlers import TargetPath, PluginType, UUID

from dcm_ip_builder.models import Target, BuildConfig, ValidationConfig
from dcm_ip_builder.plugins.mapping import MappingPlugin


def get_build_handler(
    acceptable_plugins: Mapping[str, MappingPlugin], cwd: Path
):
    """
    Returns parameterized handler (based on acceptable_plugins and cwd
    from app_config)
    """
    return Object(
        properties={
            Property("build", required=True): Object(
                model=BuildConfig,
                properties={
                    Property("target", required=True): Object(
                        model=Target,
                        properties={
                            Property("path", required=True): TargetPath(
                                _relative_to=cwd, cwd=cwd, is_dir=True
                            )
                        },
                        accept_only=["path"],
                    ),
                    Property(
                        "mappingPlugin", name="mapping_plugin", required=True
                    ): PluginType(
                        acceptable_plugins,
                        acceptable_context=["mapping"],
                    ),
                    Property("validate", default=True): Boolean(),
                    Property(
                        "BagItProfile",
                        name="bagit_profile_url",
                        # default for build is set in view function,
                        # default for validation is set in plugin instantiation
                    ): Url(),
                    Property(
                        "BagItPayloadProfile",
                        name="payload_profile_url",
                        # default for build is set in view function,
                        # default for validation is set in plugin instantiation
                    ): Url(),
                },
                accept_only=[
                    "target",
                    "mappingPlugin",
                    "validate",
                    "BagItProfile",
                    "BagItPayloadProfile",
                ],
            ),
            Property("token"): UUID(),
            Property("callbackUrl", name="callback_url"): Url(
                schemes=["http", "https"]
            ),
        },
        accept_only=["build", "token", "callbackUrl"],
    ).assemble()


def get_validate_ip_handler(cwd: Path):
    """
    Returns parameterized handler (based on cwd from app_config)
    """
    return Object(
        properties={
            Property("validation", required=True): Object(
                model=ValidationConfig,
                properties={
                    Property("target", required=True): Object(
                        model=Target,
                        properties={
                            Property("path", required=True): TargetPath(
                                _relative_to=cwd, cwd=cwd, is_dir=True
                            )
                        },
                        accept_only=["path"],
                    ),
                    Property(
                        "BagItProfile",
                        name="bagit_profile_url",
                        # default is set in plugin instantiation
                    ): Url(),
                    Property(
                        "BagItPayloadProfile",
                        name="payload_profile_url",
                        # default is set in plugin instantiation
                    ): Url(),
                },
                accept_only=["target", "BagItProfile", "BagItPayloadProfile"],
            ),
            Property("token"): UUID(),
            Property("callbackUrl", name="callback_url"): Url(
                schemes=["http", "https"]
            ),
        },
        accept_only=["validation", "token", "callbackUrl"],
    ).assemble()
