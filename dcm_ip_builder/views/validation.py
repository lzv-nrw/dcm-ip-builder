"""
Validation View-class definition
"""

from typing import Optional

from flask import Blueprint, jsonify
from data_plumber_http.decorators import flask_handler, flask_args, flask_json
from dcm_common import LoggingContext as Context
from dcm_common import services
from dcm_common.orchestration import JobConfig, Job

from dcm_ip_builder.handlers import get_validate_ip_handler
from dcm_ip_builder.models import ValidationReport, ValidationConfig
from dcm_ip_builder.plugins.validation import ValidationPluginResult


class ValidationView(services.OrchestratedView):
    """View-class for ip-validation."""

    NAME = "ip-validation"

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
            callback_url: Optional[str] = None,
        ):
            """Validate IP."""

            token = self.orchestrator.submit(
                JobConfig(
                    request_body={
                        "validation": validation.json,
                        "callback_url": callback_url
                    },
                    context=self.NAME
                )
            )
            return jsonify(token.json), 201

        self._register_abort_job(bp, "/validate")

    def get_job(self, config: JobConfig) -> Job:
        return Job(
            cmd=lambda push, data: self.validate(
                push,
                data,
                validation_config=ValidationConfig.from_json(
                    config.request_body["validation"]
                )
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

    def validate(
        self,
        push,
        report: ValidationReport,
        validation_config: ValidationConfig
    ):
        """
        Job instructions for the '/validate' endpoint.

        Orchestration standard-arguments:
        push -- (orchestration-standard) push `report` to host process
        report -- (orchestration-standard) common report-object shared
                  via `push`

        Keyword arguments:
        validation_config -- a `ValidationConfig`-object
        """

        # set progress info
        report.progress.verbose = (
            f"validating IP from '{validation_config.target.path}'"
        )
        report.log.log(
            Context.INFO,
            body=f"Validating IP '{validation_config.target.path}'."
        )
        push()

        # Create validation_plugins with empty arguments
        validation_plugins = {
            plugin_name: {
                "plugin": self.config.validation_plugins[plugin_name],
                "args": {}
            }
            for plugin_name in ["bagit-profile", "payload-structure"]
        }
        if validation_config.bagit_profile_url:
            # Register any profile url from request
            validation_plugins["bagit-profile"]["args"] = {
                "profile_url": validation_config.bagit_profile_url
            }
        if validation_config.payload_profile_url:
            # Register any profile url from request
            validation_plugins["payload-structure"]["args"] = {
                "profile_url": validation_config.payload_profile_url
            }

        # iterate validation plugins
        for config in validation_plugins.values():
            # collect plugin-info
            plugin = config["plugin"]
            report.progress.verbose = f"calling plugin '{plugin.display_name}'"
            report.log.log(
                Context.INFO, body=f"Calling plugin '{plugin.display_name}'"
            )
            push()

            # configure execution context
            context = plugin.create_context(
                report.progress.create_verbose_update_callback(
                    plugin.display_name
                ),
                push,
            )
            report.data.details[plugin.name] = context.result

            # run plugin logic
            plugin.get(
                context,
                **(
                    {"path": str(validation_config.target.path)}
                    | config["args"]
                ),
            )
            # Copy all error messages in the main log
            report.log.merge(context.result.log.pick(Context.ERROR))
            if not context.result.success:
                report.log.log(
                    Context.ERROR,
                    body=f"Call to plugin '{plugin.display_name}' failed.",
                )
            push()

        # eval and log
        report.data.success = all(
            p.success
            for p in report.data.details.values()
            if isinstance(p, ValidationPluginResult)
        )
        if report.data.success:
            report.data.valid = all(
                p.valid
                for p in report.data.details.values()
                if isinstance(p, ValidationPluginResult)
            )
            if report.data.valid:
                report.log.log(
                    Context.INFO,
                    body="Target is valid.",
                )
            else:
                plugins_with_errors = sum(
                    not p.valid for p in report.data.details.values()
                    if isinstance(p, ValidationPluginResult)
                )
                report.log.log(
                    Context.ERROR,
                    body=(
                        "Target is invalid (got errors from "
                        + f"{plugins_with_errors} "
                        + f"plugin{'s' if plugins_with_errors else ''})."
                    )
                )
        else:
            plugins_not_success = sum(
                not p.success for p in report.data.details.values()
                if isinstance(p, ValidationPluginResult)
            )
            report.log.log(
                Context.ERROR,
                body=(
                    f"Validation incomplete ({plugins_not_success} "
                    f"plugin{'s' if plugins_not_success else ''} "
                    "gave bad response)."
                )
            )
        push()
