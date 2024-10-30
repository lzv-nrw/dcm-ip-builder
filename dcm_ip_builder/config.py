"""Configuration module for the 'DCM IP Builder'-app."""

import os
from pathlib import Path
from importlib.metadata import version

import yaml
from dcm_common.util import get_profile
from dcm_common.services import FSConfig, OrchestratedAppConfig
from dcm_object_validator.models import validation_config
import dcm_ip_builder_api

import dcm_ip_builder


class AppConfig(FSConfig, OrchestratedAppConfig):
    """
    Configuration for the 'DCM IP Builder'.
    """

    # ------ COMMON ------
    # bagit profile
    BAGIT_PROFILE_URL = \
        os.environ.get("BAGIT_PROFILE_URL") \
            or "https://lzv.nrw/bagit_profile.json"
    BAGIT_PROFILE = get_profile(
        os.environ.get("BAGIT_PROFILE_URL")
        or Path(dcm_ip_builder.__file__).parent
            / "static" / "bagit_profile.json"
    )
    # payload profile
    PAYLOAD_PROFILE_URL = \
        os.environ.get("PAYLOAD_PROFILE_URL") \
            or "https://lzv.nrw/payload_profile.json"
    PAYLOAD_PROFILE = get_profile(
        os.environ.get("PAYLOAD_PROFILE_URL")
        or Path(dcm_ip_builder.__file__).parent
            / "static" / "payload_profile.json"
    )

    # ------ VALIDATION ------
    USE_OBJECT_VALIDATOR = (int(os.environ.get("USE_OBJECT_VALIDATOR") or 1)) == 1
    OBJECT_VALIDATOR_HOST = \
        os.environ.get("OBJECT_VALIDATOR_HOST") or "http://localhost:8082"
    OBJECT_VALIDATOR_VALIDATION_TIMEOUT = \
        int(os.environ.get("OBJECT_VALIDATOR_VALIDATION_TIMEOUT") or "3600")
    # define default validation options
    DEFAULT_IP_VALIDATORS = [
        validation_config.BagitProfileModule.identifier,
    ]
    DEFAULT_OBJECT_VALIDATORS = []
    DEFAULT_IP_FILE_FORMAT_PLUGINS = []
    DEFAULT_OBJECT_FILE_FORMAT_PLUGINS = []
    SUPPORTED_VALIDATOR_MODULES = DEFAULT_IP_VALIDATORS
    SUPPORTED_VALIDATOR_PLUGINS = []
    # default arguments for validator constructors
    DEFAULT_VALIDATOR_KWARGS = {
        "bagit_profile": {
            "bagit_profile_url": BAGIT_PROFILE_URL,
            "bagit_profile": BAGIT_PROFILE,
        }
    }

    # ------ BUILD ------
    IP_OUTPUT = Path("ip")
    # Algorithms for the manifest and tag-manifest files
    MANIFESTS = ["sha256", "sha512"]
    TAG_MANIFESTS = ["sha256", "sha512"]
    # Path to the file with the metadata
    META_DIRECTORY = Path("meta")
    SOURCE_METADATA = Path("source_metadata.xml")
    DC_METADATA = Path("dc.xml")
    # spec v0.3.2
    # filled by builder:
    # 'Payload-Oxum', 'Bagging-DateTime'
    # filled by build.py:
    # 'Bag-Software-Agent', 'BagIt-Profile-Identifier', 'BagIt-Payload-Profile-Identifier'
    # filled by mapper
    MAPPED_METADATA_FIELDS = [
        "Source-Organization",
        "Origin-System-Identifier", "External-Identifier",
        "DC-Creator", "DC-Title", "DC-Rights",
        "DC-Terms-Identifier", "DC-Terms-Rights", "DC-Terms-License",
        "DC-Terms-Access-Rights", "Embargo-Enddate", "DC-Terms-Rights-Holder",
        "Preservation-Level"
    ]
    # Whether to perform the validation of the generated IP
    DO_VALIDATION = True

    # Load the API document
    API_DOCUMENT = Path(dcm_ip_builder_api.__file__).parent / "openapi.yaml"
    API = yaml.load(
        API_DOCUMENT.read_text(encoding="utf-8"),
        Loader=yaml.SafeLoader
    )

    def set_identity(self) -> None:
        super().set_identity()
        self.CONTAINER_SELF_DESCRIPTION["description"] = (
            "This API provides endpoints for IP building and IP validation."
            + "Requests for unavailable validation-modules are forwarded to"
            + " an Object Validator-service."
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
            "do_validation": self.DO_VALIDATION,
        }
        settings["validation"] = {
            "default_profile": self.BAGIT_PROFILE_URL,
            "default_payload_profile": self.PAYLOAD_PROFILE_URL,
            "plugins": self.DEFAULT_IP_VALIDATORS,
            "use_object_validator": self.USE_OBJECT_VALIDATOR,
            "object_validator_timeout": {
                "duration": self.OBJECT_VALIDATOR_VALIDATION_TIMEOUT,
            }
        }
        # - plugins
        self.CONTAINER_SELF_DESCRIPTION["configuration"]["plugins"] = {
            identifier: {
                "name": identifier,
                "description":
                    validation_config.SUPPORTED_VALIDATORS[identifier].validator.VALIDATOR_TAG + ": "
                    + validation_config.SUPPORTED_VALIDATORS[identifier].validator.VALIDATOR_DESCRIPTION,
            } for identifier in self.SUPPORTED_VALIDATOR_MODULES
        }
        # - services
        self.CONTAINER_SELF_DESCRIPTION["configuration"]["services"] = {
            "Object Validator": self.OBJECT_VALIDATOR_HOST
        }
