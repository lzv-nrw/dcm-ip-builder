"""Configuration module for the 'DCM IP Builder'-app."""

from typing import Iterable
import sys
import os
from pathlib import Path
from importlib.metadata import version
import json

import yaml
from dcm_common.util import get_profile
from dcm_common.services import FSConfig, OrchestratedAppConfig
from dcm_common.plugins import PluginInterface, import_from_directory
import dcm_ip_builder_api

import dcm_ip_builder
from dcm_ip_builder.plugins.mapping import (
    DemoMappingPlugin, GenericB64Plugin, GenericUrlPlugin
)
from dcm_ip_builder.plugins import (
    BagItBagBuilder,
    BagItProfilePlugin,
    PayloadStructurePlugin,
)


def plugin_ok(plugin: type[PluginInterface]) -> bool:
    """
    Validates `plugin.requirements_met` and prints warning to stderr
    if not.
    """
    ok, msg = plugin.requirements_met()
    if not ok:
        print(
            f"WARNING: Unable to load plugin '{plugin.display_name}' "
            + f"({plugin.name}): {msg}",
            file=sys.stderr,
        )
    return ok


def load_plugins(
    plugins: Iterable[PluginInterface]
) -> dict[str, PluginInterface]:
    """Loads all provided plugins that meet their requirements."""
    return {
        Plugin.name: Plugin() for Plugin in plugins if plugin_ok(Plugin)
    }


class AppConfig(FSConfig, OrchestratedAppConfig):
    """
    Configuration for the 'DCM IP Builder'.
    """

    # ------ COMMON ------
    # bagit profile
    BAGIT_PROFILE_URL = (
        os.environ.get("BAGIT_PROFILE_URL")
        or "https://lzv.nrw/bagit_profile.json"
    )
    BAGIT_PROFILE = get_profile(
        os.environ.get("BAGIT_PROFILE_URL")
        or Path(dcm_ip_builder.__file__).parent
        / "static"
        / "bagit_profile.json"
    )
    BAGINFO_TAG_CASE_SENSITIVE = (
        (int(os.environ.get("BAGINFO_TAG_CASE_SENSITIVE") or 1)) == 1
    )
    # payload profile
    PAYLOAD_PROFILE_URL = (
        os.environ.get("PAYLOAD_PROFILE_URL")
        or "https://lzv.nrw/payload_profile.json"
    )
    PAYLOAD_PROFILE = get_profile(
        os.environ.get("PAYLOAD_PROFILE_URL")
        or Path(dcm_ip_builder.__file__).parent
        / "static"
        / "payload_profile.json"
    )

    # ------ BUILD ------
    ADDITIONAL_MAPPING_PLUGINS_DIR = (
        Path(os.environ.get("ADDITIONAL_MAPPING_PLUGINS_DIR"))
        if "ADDITIONAL_MAPPING_PLUGINS_DIR" in os.environ
        else None
    )
    ALLOW_GENERIC_MAPPING = (
        int(os.environ.get("ALLOW_GENERIC_MAPPING") or 0)
    ) == 1
    USE_DEMO_PLUGIN = int(os.environ.get("USE_DEMO_PLUGIN") or 0) == 1
    MAPPING_PLUGINS = [] + (
        [GenericB64Plugin, GenericUrlPlugin] if ALLOW_GENERIC_MAPPING else []
    ) + (
        [DemoMappingPlugin] if USE_DEMO_PLUGIN else []
    )
    IP_OUTPUT = Path("ip")
    DO_VALIDATION = True
    # Algorithms for the manifest and tag-manifest files
    MANIFESTS = (
        json.loads(os.environ["MANIFESTS"])
        if "MANIFESTS" in os.environ
        else ["sha256", "sha512"]
    )
    TAG_MANIFESTS = (
        json.loads(os.environ["TAG_MANIFESTS"])
        if "TAG_MANIFESTS" in os.environ
        else ["sha256", "sha512"]
    )
    # Path to the file with the metadata
    META_DIRECTORY = Path("meta")
    SOURCE_METADATA = Path("source_metadata.xml")
    DC_METADATA = Path("dc.xml")

    # Load the API document
    API_DOCUMENT = Path(dcm_ip_builder_api.__file__).parent / "openapi.yaml"
    API = yaml.load(
        API_DOCUMENT.read_text(encoding="utf-8"),
        Loader=yaml.SafeLoader
    )

    def __init__(self) -> None:
        # initialize plugins
        # ------ BUILD ------
        self.mapping_plugins = load_plugins(self.MAPPING_PLUGINS)
        if self.ADDITIONAL_MAPPING_PLUGINS_DIR is not None:
            self.mapping_plugins.update(
                import_from_directory(
                    self.ADDITIONAL_MAPPING_PLUGINS_DIR,
                    lambda p: p.context == "mapping" and plugin_ok(p),
                )
            )
        self.build_plugin = BagItBagBuilder(
            working_dir=self.FS_MOUNT_POINT,
            manifests=self.MANIFESTS,
            tagmanifests=self.TAG_MANIFESTS
        )
        # ------ VALIDATION ------
        self.validation_plugins = {
            BagItProfilePlugin.name: BagItProfilePlugin(
                default_profile_url=self.BAGIT_PROFILE_URL,
                default_profile=self.BAGIT_PROFILE,
                baginfo_tag_case_sensitive=self.BAGINFO_TAG_CASE_SENSITIVE
            ),
            PayloadStructurePlugin.name: PayloadStructurePlugin(
                default_profile_url=self.PAYLOAD_PROFILE_URL,
                default_profile=self.PAYLOAD_PROFILE
            ),
        }
        super().__init__()

    def set_identity(self) -> None:
        super().set_identity()
        self.CONTAINER_SELF_DESCRIPTION["description"] = (
            "This API provides endpoints for IP building and IP validation."
        )

        # version
        self.CONTAINER_SELF_DESCRIPTION["version"]["api"] = (
            self.API["info"]["version"]
        )
        self.CONTAINER_SELF_DESCRIPTION["version"]["app"] = version(
            "dcm-ip-builder"
        )
        self.CONTAINER_SELF_DESCRIPTION["version"]["profile"] = (
            self.BAGIT_PROFILE["BagIt-Profile-Info"]["Version"]
        )
        self.CONTAINER_SELF_DESCRIPTION["version"]["profile_payload"] = (
            self.PAYLOAD_PROFILE["BagIt-Payload-Profile-Info"]["Version"]
        )

        # configuration
        # - settings
        settings = self.CONTAINER_SELF_DESCRIPTION["configuration"]["settings"]
        settings["build"] = {
            "output": str(self.IP_OUTPUT),
            "manifest": self.MANIFESTS,
            "tag_manifest": self.TAG_MANIFESTS,
            "default_profile": self.BAGIT_PROFILE_URL,
            "default_payload_profile": self.PAYLOAD_PROFILE_URL,
            "do_validation": self.DO_VALIDATION
        }
        settings["validation"] = {
            "default_profile": self.BAGIT_PROFILE_URL,
            "default_payload_profile": self.PAYLOAD_PROFILE_URL,
            "plugins": list(self.validation_plugins.keys()),
        }
        # - plugins
        self.CONTAINER_SELF_DESCRIPTION["configuration"]["plugins"] = {
            plugin.name: plugin.json
            for plugin in self.mapping_plugins.values()
        }
