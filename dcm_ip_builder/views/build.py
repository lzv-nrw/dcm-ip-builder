"""
Build View-class definition
"""

from typing import Optional
from importlib.metadata import version
from pathlib import Path

from lxml import etree as et
from flask import Blueprint, jsonify
from data_plumber_http.decorators import flask_handler, flask_args, flask_json
from dcm_common import LoggingContext as Context
from dcm_common.util import get_output_path
from dcm_common.orchestration import JobConfig, Job
from dcm_common import services
from dcm_common.services.plugins import PluginConfig

from dcm_ip_builder.config import AppConfig
from dcm_ip_builder.models import (
    BuildConfig,
    BuildReport,
    Target,
    ValidationConfig,
)
from dcm_ip_builder.handlers import get_build_handler
from dcm_ip_builder.views.validation import ValidationView


class BuildView(services.OrchestratedView):
    """View-class for ip-building."""

    NAME = "ip-build"

    def __init__(
        self, config: AppConfig, *args, **kwargs
    ) -> None:
        super().__init__(config, *args, **kwargs)

    def configure_bp(self, bp: Blueprint, *args, **kwargs) -> None:
        @bp.route("/build", methods=["POST"])
        @flask_handler(  # unknown query
            handler=services.no_args_handler,
            json=flask_args,
        )
        @flask_handler(  # process ip-build
            handler=get_build_handler(
                acceptable_plugins=self.config.mapping_plugins,
                cwd=self.config.FS_MOUNT_POINT
            ),
            json=flask_json,
        )
        def build(
            build: BuildConfig,
            callback_url: Optional[str] = None
        ):
            """Submit IE for IP building."""

            token = self.orchestrator.submit(
                JobConfig(
                    request_body={
                        "build": build.json,
                        "callback_url": callback_url
                    },
                    context=self.NAME
                )
            )
            return jsonify(token.json), 201

        self._register_abort_job(bp, "/build")

    def get_job(self, config: JobConfig) -> Job:
        return Job(
            cmd=lambda push, data: self.build(
                push, data,
                build_config=BuildConfig(
                    target=Target.from_json(
                        config.request_body["build"]["target"]
                    ),
                    mapping_plugin=PluginConfig.from_json(
                        config.request_body["build"]["mapping_plugin"]
                    ),
                    validate=config.request_body["build"]["validate"],
                    bagit_profile_url=(
                        config.request_body["build"].get(
                            "bagit_profile_url", None
                        )
                    ),
                    payload_profile_url=(
                        config.request_body["build"].get(
                            "payload_profile_url", None
                        )
                    ),
                ),
            ),
            hooks={
                "startup": services.default_startup_hook,
                "success": services.default_success_hook,
                "fail": services.default_fail_hook,
                "abort": services.default_abort_hook,
                "completion": services.termination_callback_hook_factory(
                    config.request_body.get("callback_url", None),
                )
            },
            name="IP Builder"
        )

    def build(
        self, push, report: BuildReport,
        build_config: BuildConfig
    ):
        """
        Job instructions for the '/build' endpoint.

        Orchestration standard-arguments:
        push -- (orchestration-standard) push `report` to host process
        report -- (orchestration-standard) common report-object shared
                  via `push`

        Keyword arguments:
        build_config -- a `BuildConfig`-config
        """

        # set progress info
        report.progress.verbose = (
            f"building IP from '{build_config.target.path}'"
        )
        report.log.log(
            Context.INFO,
            body=f"Building IP from IE '{build_config.target.path}'."
        )
        push()

        # Create IP_path for the bag or exit if not successful
        report.data.path = get_output_path(
            self.config.IP_OUTPUT
        )
        if report.data.path is None:
            report.data.success = False
            report.log.log(
                Context.ERROR,
                body="Unable to generate output directory in "
                + f"'{self.config.FS_MOUNT_POINT / self.config.IP_OUTPUT}'"
                + "(maximum retries exceeded)."
            )
            push()
            return
        report.log.log(
            Context.INFO,
            body=f"Building IP at '{report.data.path}'."
        )
        push()

        # Generate metadata-subset for bag-info.txt
        # prepare plugin-call by linking data
        plugin = self.config.mapping_plugins[
            build_config.mapping_plugin.plugin
        ]
        report.data.details["mapping"] = plugin.get(
            None,
            **(
                build_config.mapping_plugin.args
                | {
                    "path": build_config.target.path
                    / self.config.META_DIRECTORY
                    / self.config.SOURCE_METADATA
                }
            ),
        )
        report.log.merge(report.data.details["mapping"].log)
        if not report.data.details["mapping"].success:
            report.log.log(
                Context.ERROR,
                body="Mapping-plugin did not succeed, cannot continue."
            )
            report.data.success = False
            push()
            return

        # Provide additional information for bag-info
        if not report.data.details["mapping"].metadata:
            report.data.details["mapping"].metadata = {}
            report.log.log(
                Context.WARNING,
                body="Received empty bag-info from mapping plugin."
            )
            push()
        report.data.details["mapping"].metadata.update(
            {
                "Bag-Software-Agent": (
                    f"dcm-ip-builder v{version('dcm-ip-builder')}"
                ),
                "BagIt-Profile-Identifier": (
                    build_config.bagit_profile_url
                    or self.config.BAGIT_PROFILE_URL
                ),
                "BagIt-Payload-Profile-Identifier": (
                    build_config.payload_profile_url
                    or self.config.PAYLOAD_PROFILE_URL
                ),
            }
        )
        push()

        # Build IP and append plugin result into details
        report.data.details["build"] = self.config.build_plugin.get(
            None,
            src=str(build_config.target.path),
            bag_info=report.data.details["mapping"].metadata,
            dest=str(report.data.path),
            exist_ok=True
        )
        report.log.merge(report.data.details["build"].log)
        push()

        # exit if building failed
        if not report.data.details["build"].success:
            report.data.success = False
            report.log.log(
                Context.ERROR,
                body=f"Building IP from IE '{build_config.target.path}' "
                + "failed."
            )
            push()
            return

        # Prepare dc.xml
        if self.generate_dc_xml(
            build_config.target.path
                / self.config.META_DIRECTORY
                / self.config.SOURCE_METADATA,
            report.data.path
                / self.config.META_DIRECTORY
                / self.config.DC_METADATA
        ):
            report.log.log(
                Context.INFO,
                body="DC-Metadata detected, '"
                + str(self.config.META_DIRECTORY / self.config.DC_METADATA)
                + "' written."
            )
            push()

        report.log.log(
            Context.INFO,
            body="Successfully assembled IP at "
            + f"'{report.data.path}'."
        )
        push()

        # validate IP, if required
        if build_config.validate:
            ValidationView(self.config).validate(
                push,
                report=report,
                validation_config=ValidationConfig(
                    target=Target(path=report.data.path),
                    bagit_profile_url=build_config.bagit_profile_url,
                    payload_profile_url=build_config.payload_profile_url
                ),
            )
            if not report.data.valid:
                report.data.success = False
            else:
                report.data.success = True
        else:
            report.data.success = True
        push()

    def generate_dc_xml(self, src_path: Path, dest_path: Path) -> bool:
        """
        Prepare dc.xml.

        Returns `True` if `dc.xml` has been created.

        Keyword arguments
        src_path -- path to metadata source file
        dest_path -- path to output file
        """

        if not src_path.is_file():
            return False

        # Select a parser and make it remove whitespace
        # to discard xml file formatting from the source file
        parser = et.XMLParser(remove_blank_text=True)
        # Get the element tree of the source file
        src_tree = et.parse(
            src_path,
            parser
        )
        # From anywhere in the source document
        # find the tag "oai_dc:dc" to copy in dc.xml
        src_tag = src_tree.find(
            ".//{http://www.openarchives.org/OAI/2.0/oai_dc/}dc"
        )
        if src_tag is not None:
            # Get the dc-element tree of the destination file and write to
            # dest_path
            et.ElementTree(src_tag).write(
                dest_path, xml_declaration=True,
                encoding="UTF-8", pretty_print=True
            )
            return True
        return False
