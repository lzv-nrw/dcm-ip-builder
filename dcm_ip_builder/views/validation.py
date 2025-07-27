"""
Validation View-class definition
"""

from typing import Optional
from pathlib import Path
import os
from uuid import uuid4

from flask import Blueprint, jsonify, Response, request
import bagit_utils
from data_plumber_http.decorators import flask_handler, flask_args, flask_json
from dcm_common import LoggingContext as Context
from dcm_common import services
from dcm_common.orchestra import JobConfig, JobContext, JobInfo

from dcm_ip_builder.handlers import get_validate_ip_handler
from dcm_ip_builder.models import ValidationReport, ValidationConfig
from dcm_ip_builder.plugins.validation import ValidationPluginResult


class ValidationView(services.OrchestratedView):
    """View-class for ip-validation."""

    NAME = "ip-validation"

    def register_job_types(self):
        self.config.worker_pool.register_job_type(
            self.NAME, self.validate, ValidationReport
        )

    def configure_bp(self, bp: Blueprint, *args, **kwargs) -> None:

        @bp.route("/validate", methods=["POST"])
        @flask_handler(  # unknown query
            handler=services.no_args_handler,
            json=flask_args,
        )
        @flask_handler(  # process validation
            handler=get_validate_ip_handler(cwd=self.config.FS_MOUNT_POINT),
            json=flask_json,
        )
        def validate(
            validation: ValidationConfig,
            token: Optional[str] = None,
            callback_url: Optional[str] = None,
        ):
            """Validate IP."""
            try:
                token = self.config.controller.queue_push(
                    token or str(uuid4()),
                    JobInfo(
                        JobConfig(
                            self.NAME,
                            original_body=request.json,
                            request_body={
                                "validation": validation.json,
                                "callback_url": callback_url,
                            },
                        ),
                        report=ValidationReport(
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

        self._register_abort_job(bp, "/validate")

    def load_identifiers(self, path: Path, report: ValidationReport) -> None:
        """
        Loads identifiers from IP-metadata into `report.data`. Fails
        silently.
        """
        try:
            baginfo = bagit_utils.Bag(path, load=False).baginfo
        except bagit_utils.BagItError as exc_info:
            # log but do not change 'valid'-flag
            # (validation is done by custom request)
            report.log.log(
                Context.ERROR,
                body=f"Unable to load IP-identifiers: {exc_info}",
            )
        else:
            (report.data.external_id,) = baginfo.get(
                "External-Identifier", [None]
            )
            (report.data.origin_system_id,) = baginfo.get(
                "Origin-System-Identifier", [None]
            )

    def validate(
        self,
        context: JobContext,
        info: JobInfo,
        validation_config: Optional[ValidationConfig] = None,
    ):
        """Job instructions for the '/validate' endpoint."""
        # this enables re-usability in build-endpoint
        if validation_config is None:
            os.chdir(self.config.FS_MOUNT_POINT)
            _validation_config = ValidationConfig.from_json(
                info.config.request_body["validation"]
            )
            info.report.log.set_default_origin("IP Builder")
        else:
            _validation_config = validation_config

        # set progress info
        info.report.progress.verbose = (
            f"validating IP from '{_validation_config.target.path}'"
        )
        info.report.log.log(
            Context.INFO,
            body=f"Validating IP '{_validation_config.target.path}'.",
        )
        context.push()

        # Create validation_plugins with empty arguments
        validation_plugins = {
            plugin_name: {
                "plugin": self.config.validation_plugins[plugin_name],
                "args": {},
            }
            for plugin_name in [
                "bagit-profile",
                "payload-structure",
                "significant-properties",
            ]
        }
        if _validation_config.bagit_profile_url:
            # Register any profile url from request
            validation_plugins["bagit-profile"]["args"] = {
                "profile_url": _validation_config.bagit_profile_url
            }
        if _validation_config.payload_profile_url:
            # Register any profile url from request
            validation_plugins["payload-structure"]["args"] = {
                "profile_url": _validation_config.payload_profile_url
            }

        # iterate validation plugins
        for config in validation_plugins.values():
            # collect plugin-info
            plugin = config["plugin"]
            info.report.progress.verbose = (
                f"calling plugin '{plugin.display_name}'"
            )
            info.report.log.log(
                Context.INFO, body=f"Calling plugin '{plugin.display_name}'"
            )
            context.push()

            # configure execution context
            context = plugin.create_context(
                info.report.progress.create_verbose_update_callback(
                    plugin.display_name
                ),
                context.push,
            )
            info.report.data.details[plugin.name] = context.result

            # run plugin logic
            plugin.get(
                context,
                **(
                    {"path": str(_validation_config.target.path)}
                    | config["args"]
                ),
            )
            # Copy messages into main log
            info.report.log.merge(
                context.result.log
            )

            if not context.result.success:
                info.report.log.log(
                    Context.ERROR,
                    body=f"Call to plugin '{plugin.display_name}' failed.",
                )
            context.push()

        # eval and log
        info.report.data.success = all(
            p.success
            for p in info.report.data.details.values()
            if isinstance(p, ValidationPluginResult)
        )
        if info.report.data.success:
            info.report.data.valid = all(
                p.valid
                for p in info.report.data.details.values()
                if isinstance(p, ValidationPluginResult)
            )
            if info.report.data.valid:
                info.report.log.log(
                    Context.INFO,
                    body="Target is valid.",
                )
                self.load_identifiers(
                    _validation_config.target.path, info.report
                )
            else:
                plugins_with_errors = sum(
                    not p.valid
                    for p in info.report.data.details.values()
                    if isinstance(p, ValidationPluginResult)
                )
                info.report.log.log(
                    Context.ERROR,
                    body=(
                        "Target is invalid (got errors from "
                        + f"{plugins_with_errors} "
                        + f"plugin{'s' if plugins_with_errors else ''})."
                    ),
                )
        else:
            plugins_not_success = sum(
                not p.success
                for p in info.report.data.details.values()
                if isinstance(p, ValidationPluginResult)
            )
            info.report.log.log(
                Context.ERROR,
                body=(
                    f"Validation incomplete ({plugins_not_success} "
                    f"plugin{'s' if plugins_not_success else ''} "
                    "gave bad response)."
                ),
            )
        context.push()

        # make callback; rely on _run_callback to push progress-update
        # (only if plain validation)
        if validation_config is None:
            info.report.progress.complete()
            self._run_callback(
                context, info, info.config.request_body.get("callback_url")
            )
