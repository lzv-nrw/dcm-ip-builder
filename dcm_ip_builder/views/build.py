"""
Build View-class definition
"""

from typing import Optional
from importlib.metadata import version
from pathlib import Path
import os
from uuid import uuid4

from lxml import etree as et
from flask import Blueprint, jsonify, Response, request
from data_plumber_http.decorators import flask_handler, flask_args, flask_json
from dcm_common import LoggingContext as Context
from dcm_common.util import get_output_path
from dcm_common.orchestra import JobConfig, JobContext, JobInfo
from dcm_common import services

from dcm_ip_builder.models import (
    BuildConfig,
    BuildReport,
    Target,
    ValidationConfig,
)
from dcm_ip_builder.handlers import get_build_handler
from dcm_ip_builder.components import Bag
from dcm_ip_builder.views.validation import ValidationView


class BuildView(services.OrchestratedView):
    """View-class for ip-building."""

    NAME = "ip-build"

    def register_job_types(self):
        self.config.worker_pool.register_job_type(
            self.NAME, self.build, BuildReport
        )

    def configure_bp(self, bp: Blueprint, *args, **kwargs) -> None:
        @bp.route("/build", methods=["POST"])
        @flask_handler(  # unknown query
            handler=services.no_args_handler,
            json=flask_args,
        )
        @flask_handler(  # process ip-build
            handler=get_build_handler(
                acceptable_plugins=self.config.mapping_plugins,
                cwd=self.config.FS_MOUNT_POINT,
            ),
            json=flask_json,
        )
        def build(
            build: BuildConfig,
            token: Optional[str] = None,
            callback_url: Optional[str] = None,
        ):
            """Submit IE for IP building."""
            try:
                token = self.config.controller.queue_push(
                    token or str(uuid4()),
                    JobInfo(
                        JobConfig(
                            self.NAME,
                            original_body=request.json,
                            request_body={
                                "build": build.json,
                                "callback_url": callback_url,
                            },
                        ),
                        report=BuildReport(
                            host=request.host_url, args=request.json
                        ),
                    ),
                )
            # pylint: disable=broad-exception-caught
            except Exception as exc_info:
                return Response(
                    f"Submission rejected: {exc_info}",
                    mimetype="text/plain",
                    status=500,
                )

            return jsonify(token.json), 201

        self._register_abort_job(bp, "/build")

    def build(self, context: JobContext, info: JobInfo):
        """Job instructions for the '/build' endpoint."""
        os.chdir(self.config.FS_MOUNT_POINT)
        build_config = BuildConfig.from_json(info.config.request_body["build"])
        info.report.log.set_default_origin("IP Builder")

        # set progress info
        info.report.progress.verbose = (
            f"building IP from '{build_config.target.path}'"
        )
        info.report.log.log(
            Context.INFO,
            body=f"Building IP from IE '{build_config.target.path}'.",
        )
        context.push()

        # Create IP_path for the bag or exit if not successful
        info.report.data.path = get_output_path(self.config.IP_OUTPUT)
        if info.report.data.path is None:
            info.report.data.success = False
            info.report.log.log(
                Context.ERROR,
                body="Unable to generate output directory in "
                + f"'{self.config.FS_MOUNT_POINT / self.config.IP_OUTPUT}'"
                + "(maximum retries exceeded).",
            )
            context.push()
            # make callback; rely on _run_callback to push progress-update
            info.report.progress.complete()
            self._run_callback(
                context, info, info.config.request_body.get("callback_url")
            )
            return
        info.report.log.log(
            Context.INFO, body=f"Building IP at '{info.report.data.path}'."
        )
        context.push()

        # Generate metadata-subset for bag-info.txt
        # prepare plugin-call by linking data
        plugin = self.config.mapping_plugins[
            build_config.mapping_plugin.plugin
        ]
        info.report.data.details["mapping"] = plugin.get(
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
        info.report.log.merge(info.report.data.details["mapping"].log)
        if not info.report.data.details["mapping"].success:
            info.report.log.log(
                Context.ERROR,
                body="Mapping-plugin did not succeed, cannot continue.",
            )
            info.report.data.success = False
            context.push()
            # make callback; rely on _run_callback to push progress-update
            info.report.progress.complete()
            self._run_callback(
                context, info, info.config.request_body.get("callback_url")
            )
            return

        # Provide additional information for bag-info
        if not info.report.data.details["mapping"].metadata:
            info.report.data.details["mapping"].metadata = {}
            info.report.log.log(
                Context.WARNING,
                body="Received empty bag-info from mapping plugin.",
            )
            context.push()
        info.report.data.details["mapping"].metadata.update(
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
        context.push()

        # Build IP and append plugin result into details
        info.report.data.details["build"] = self.config.build_plugin.get(
            None,
            src=str(build_config.target.path),
            bag_info=info.report.data.details["mapping"].metadata,
            dest=str(info.report.data.path),
            exist_ok=True,
        )
        info.report.log.merge(info.report.data.details["build"].log)
        context.push()

        # exit if building failed
        if not info.report.data.details["build"].success:
            info.report.data.success = False
            info.report.log.log(
                Context.ERROR,
                body=f"Building IP from IE '{build_config.target.path}' "
                + "failed.",
            )
            context.push()
            # make callback; rely on _run_callback to push progress-update
            info.report.progress.complete()
            self._run_callback(
                context, info, info.config.request_body.get("callback_url")
            )
            return

        # Prepare dc.xml
        if self.generate_dc_xml(
            build_config.target.path
            / self.config.META_DIRECTORY
            / self.config.SOURCE_METADATA,
            info.report.data.path
            / self.config.META_DIRECTORY
            / self.config.DC_METADATA,
        ):
            # Generate new tag-manifest files
            Bag(info.report.data.path, load=False).set_tag_manifests()
            info.report.log.log(
                Context.INFO,
                body="DC-Metadata detected, '"
                + str(self.config.META_DIRECTORY / self.config.DC_METADATA)
                + "' written.",
            )
            context.push()

        info.report.log.log(
            Context.INFO,
            body="Successfully assembled IP at "
            + f"'{info.report.data.path}'.",
        )
        context.push()

        # validate IP, if required
        if build_config.validate:
            ValidationView(self.config).validate(
                context,
                info,
                validation_config=ValidationConfig(
                    target=Target(path=info.report.data.path),
                    bagit_profile_url=build_config.bagit_profile_url,
                    payload_profile_url=build_config.payload_profile_url,
                ),
            )
            if not info.report.data.valid:
                info.report.data.success = False
            else:
                info.report.data.success = True
        else:
            info.report.data.success = True
        context.push()

        # make callback; rely on _run_callback to push progress-update
        info.report.progress.complete()
        self._run_callback(
            context, info, info.config.request_body.get("callback_url")
        )

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
        src_tree = et.parse(src_path, parser)
        # From anywhere in the source document
        # find the tag "oai_dc:dc" to copy in dc.xml
        src_tag = src_tree.find(
            ".//{http://www.openarchives.org/OAI/2.0/oai_dc/}dc"
        )
        if src_tag is not None:
            # Get the dc-element tree of the destination file and write to
            # dest_path
            et.ElementTree(src_tag).write(
                dest_path,
                xml_declaration=True,
                encoding="UTF-8",
                pretty_print=True,
            )
            return True
        return False
