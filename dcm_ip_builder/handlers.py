"""Input handlers for the 'DCM IP Builder'-app."""

from typing import Any
from pathlib import Path
from urllib import request
import importlib
import base64

from data_plumber_http import (
    Property, Object, String, Url, Boolean, Array, DPType
)
from data_plumber_http.settings import Responses
from dcm_s11n.vinegar import Vinegar
from dcm_common.services.handlers import TargetPath

from dcm_ip_builder.models.build_config import _BuildConfig
from dcm_ip_builder.models import Target


class MapperConverterConfig(DPType):
    TYPE = str

    @staticmethod
    def try_loading_config(config_str: str, loc: str) -> tuple[Any, str, int]:
        """Helper function for build.configuration-Pipeline."""
        # validate whether config is given as url
        response = Url(schemes=["http", "https", "file", "sftp", "ftp"]).make(
            config_str, loc
        )
        if response[2] == Responses.GOOD.status:
            try:
                # get url filename
                file_name = config_str.split("/")[-1]
                # Open the url and read the bytestring
                with request.urlopen(config_str, timeout=10) as remote_file:
                    url_src = remote_file.read()
            except Exception as exc_info:
                return (
                    None,
                    f"Unable to load config-url in '{loc}': {str(exc_info)}",
                    404
                )
            try:
                # Create ModuleSpec instance
                spec = importlib.util.spec_from_loader(
                    name=file_name.split(".")[0],
                    loader=None,
                    origin=config_str
                )
                # Create module
                module = importlib.util.module_from_spec(spec)
                # Execute the code
                # TODO minimize security risks from using exec
                # pylint: disable-next=exec-used
                exec(url_src, module.__dict__)
                return module.BuildConfig, "", Responses.GOOD.status
            except Exception as exc_info:
                return (None, f"ImportError at '{loc}': {str(exc_info)}", 422)
        else:
            try:
                # De-serialize the config object
                module_string = base64.b64decode(config_str)
            except Exception as exc_info:
                return (
                    None,
                    f"base64-DecodeError at '{loc}': {str(exc_info)}",
                    400
                )
            try:
                # De-serialize the config object
                module = Vinegar(None).loads(module_string)
                return module, "", Responses.GOOD.status
            except Exception as exc_info:
                return (
                    None,
                    f"DeserializationError at '{loc}': {str(exc_info)}",
                    400
                )

    def make(self, json, loc: str) -> tuple[Any, str, int]:
        # load the config and validate its attributes
        config_class, msg, status = self.try_loading_config(json, loc)
        if status != Responses.GOOD.status:
            return (None, msg, status)
        if not hasattr(config_class, "CONVERTER"):
            return (None, f"Missing property 'CONVERTER' in '{loc}'.", 422)
        if not hasattr(config_class, "MAPPER"):
            return (None, f"Missing property 'MAPPER' in '{loc}'.", 422)
        if not hasattr(config_class.CONVERTER, "get_dict"):
            return (
                None,
                f"Missing property 'get_dict' in '{loc}.CONVERTER'.",
                422
            )
        if not hasattr(config_class.MAPPER, "get_metadata"):
            return (
                None,
                f"Missing property 'get_metadata' in '{loc}.MAPPER'.",
                422
            )
        # TODO: validate callable and correct call arg signatures

        # return the json (it will be deserialized in the view-function)
        return (json, "", Responses.GOOD.status)


class BooleanModulesUseDefault(DPType):
    TYPE = list
    def make(self, json, loc: str) -> tuple[Any, str, int]:
        return (json is None, "", Responses.GOOD.status)


def get_build_handler(
    cwd: Path,
    default_modules: list[str],
    default_bagit_profile_url: str,
    default_payload_profile_url: str
):
    """
    Returns parameterized handler (based on cwd, and default modules
    and bagit profiles from app_config)
    """
    return Object(
        properties={
            Property("build", required=True): Object(
                model=_BuildConfig,
                properties={
                    Property("target", required=True): Object(
                        model=Target,
                        properties={
                            Property("path", required=True):
                                TargetPath(
                                    _relative_to=cwd, cwd=cwd, is_dir=True
                                )
                        },
                        accept_only=["path"]
                    ),
                    Property("configuration", name="config", required=True):
                        MapperConverterConfig(),
                    Property(
                        "BagItProfile",
                        name="bagit_profile_url",
                        default=default_bagit_profile_url
                    ): Url(),
                    Property(
                        "BagItPayloadProfile",
                        name="payload_profile_url",
                        default=default_payload_profile_url
                    ): Url(),
                },
                accept_only=[
                    "target", "configuration", "BagItProfile",
                    "BagItPayloadProfile",
                ]
            ),
            Property(
                "validation", default=lambda **kwargs: {
                    "modules": default_modules,
                    "modules_use_default": True
                }
            ): Object(
                properties={
                    Property("modules", default=default_modules):
                        Array(items=String()),
                    Property(  # generate additional flag 'modules_use_default'
                        "modules", name="modules_use_default", default=True
                    ): BooleanModulesUseDefault(),
                    Property("args"): Object(
                        properties={
                            Property("bagit_profile"): Object(
                                properties={
                                    Property(
                                        "profileUrl",
                                        name="payload_profile_url"
                                    ): Url(),
                                    Property(
                                        "baginfoTagCaseSensitive",
                                        name="ignore_baginfo_tag_case",
                                        default=True
                                    ): Boolean(),
                                },
                                accept_only=[
                                    "profileUrl", "baginfoTagCaseSensitive"
                                ]
                            ),
                            Property("payload_structure"): Object(
                                properties={
                                    Property(
                                        "profileUrl",
                                        name="payload_profile_url"
                                    ): Url(),
                                },
                                accept_only=["profileUrl"]
                            )
                        },
                        accept_only=["bagit_profile", "payload_structure"]
                    ),
                },
                accept_only=["target", "modules", "args"]
            ),
            Property("callbackUrl", name="callback_url"):
                Url(schemes=["http", "https"])
        },
        accept_only=["build", "validation", "callbackUrl"]
    ).assemble()


def get_validate_ip_handler(
    cwd: Path,
    default_modules: list[str],
    default_bagit_profile_url: str,
    default_payload_profile_url: str
):
    """
    Returns parameterized handler (based on cwd, and default modules
    and bagit profiles from app_config)
    """
    return Object(
        properties={
            Property("validation", required=True): Object(
                properties={
                    Property("target", required=True): Object(
                        model=Target,
                        properties={
                            Property("path", required=True):
                                TargetPath(
                                    _relative_to=cwd, cwd=cwd, is_dir=True
                                )
                        },
                        accept_only=["path"]
                    ),
                    Property("modules", default=default_modules):
                        Array(items=String()),
                    Property(  # generate additional flag 'modules_use_default'
                        "modules", name="modules_use_default", default=True
                    ): BooleanModulesUseDefault(),
                    Property("args"): Object(
                        properties={
                            Property("bagit_profile"): Object(
                                properties={
                                    Property(
                                        "profileUrl",
                                        name="bagit_profile",
                                        default=default_bagit_profile_url
                                    ): Url(),
                                    Property(
                                        "baginfoTagCaseSensitive",
                                        name="ignore_baginfo_tag_case",
                                        default=True
                                    ): Boolean(),
                                },
                                accept_only=[
                                    "profileUrl", "baginfoTagCaseSensitive"
                                ]
                            ),
                            Property("payload_structure"): Object(
                                properties={
                                    Property(
                                        "profileUrl",
                                        name="payload_profile_url",
                                        default=default_payload_profile_url
                                    ): Url(),
                                },
                                accept_only=["profileUrl"]
                            )
                        },
                        accept_only=["bagit_profile", "payload_structure"]
                    ),
                },
                accept_only=["target", "modules", "args"]
            ),
            Property("callbackUrl", name="callback_url"):
                Url(schemes=["http", "https"])
        },
        accept_only=["validation", "callbackUrl"]
    ).assemble()
