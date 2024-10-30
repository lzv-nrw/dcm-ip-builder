"""
Validation View-class definition
"""

from typing import Optional
from pathlib import Path
from time import sleep
import json

import urllib3
from flask import Blueprint, jsonify
from data_plumber_http.decorators import flask_handler, flask_args, flask_json
from dcm_common import LoggingContext as Context, LogMessage
from dcm_common import services
from dcm_common.orchestration import JobConfig, Job, Children, ChildJobEx
from dcm_object_validator.views.validation \
    import validate as validate_native
from dcm_object_validator.models import ValidationConfig
from dcm_object_validator.models.validation_modules \
    import complete_validator_kwargs
import dcm_object_validator_sdk

from dcm_ip_builder.config import AppConfig
from dcm_ip_builder.handlers import get_validate_ip_handler
from dcm_ip_builder.models import ValidationReport, Target


class ValidationView(services.OrchestratedView):
    """View-class for ip-validation."""

    NAME = "ip-validation"

    def __init__(
        self, config: AppConfig, *args, **kwargs
    ) -> None:
        super().__init__(config, *args, **kwargs)

        # object-validator sdk
        if self.config.USE_OBJECT_VALIDATOR:
            configuration = dcm_object_validator_sdk.Configuration(
                host=self.config.OBJECT_VALIDATOR_HOST
            )
            self.object_validator_validation_api = \
                dcm_object_validator_sdk.ValidationApi(
                    dcm_object_validator_sdk.ApiClient(configuration)
                )
        else:
            self.object_validator_validation_api = None

    def configure_bp(self, bp: Blueprint, *args, **kwargs) -> None:
        @bp.route("/validate/ip", methods=["POST"])
        @flask_handler(  # unknown query
            handler=services.no_args_handler,
            json=flask_args,
        )
        @flask_handler(  # process validation
            handler=get_validate_ip_handler(
                cwd=self.config.FS_MOUNT_POINT,
                default_modules=(
                    self.config.DEFAULT_IP_VALIDATORS
                    + self.config.DEFAULT_IP_FILE_FORMAT_PLUGINS
                ),
                default_bagit_profile_url=self.config.BAGIT_PROFILE_URL,
                default_payload_profile_url=self.config.PAYLOAD_PROFILE_URL
            ),
            json=flask_json,
        )
        def validate_ip(
            validation: dict,
            callback_url: Optional[str] = None
        ):
            """Validate IP."""

            token = self.orchestrator.submit(
                JobConfig(
                    request_body={
                        "validation": validation,
                        "callback_url": callback_url
                    },
                    context=self.NAME
                )
            )
            return jsonify(token.json), 201

        self._register_abort_job(bp, "/validate")

    def get_job(self, config: JobConfig) -> Job:
        # load default kwargs if missing in request
        _validator_kwargs = complete_validator_kwargs(
            config.request_body["validation"].get("args", {}),
            self.config.DEFAULT_VALIDATOR_KWARGS
        )
        # process module-selection
        validation = ValidationConfig(
            allowed=(
                self.config.DEFAULT_IP_VALIDATORS
                + self.config.DEFAULT_IP_FILE_FORMAT_PLUGINS
            ),
            modules=config.request_body["validation"]["modules"],
            kwargs=_validator_kwargs
        )
        return Job(
            cmd=lambda push, data, children: self.validate_ip(
                push, data, children,
                target=Target(
                    path=Path(
                        config.request_body["validation"]["target"]["path"]
                    ),
                    validation=data.data
                ),
                validation_config=validation,
                modules_use_default=(
                    config.request_body["validation"]["modules_use_default"]
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

    def validate_ip(
        self, push, report, children: Children,
        target: Target,
        validation_config: ValidationConfig,
        modules_use_default: bool
    ):
        """
        Job instructions for the '/validate/ip' endpoint.

        Orchestration standard-arguments:
        push -- (orchestration-standard) push `report` to host process
        report -- (orchestration-standard) common report-object shared
                  via `push`
        children -- (orchestration-standard) `ChildJob`-registry shared
                    via `push`

        Keyword arguments:
        target --  a `Target` object related to the request
        validation_config -- a `ValidationConfig`-config
        modules_use_default -- if `True`, make the Object Validator-request
                               with `modules=None`, use rejections otherwise
        """

        # set progress info
        report.progress.verbose = (
            f"validating IP from '{target.path}'"
        )
        report.log.log(
            Context.INFO,
            body=f"Validating IP '{target.path}'."
        )
        push()

        # perform native validation
        validate_native(
            push=push,
            target=target,
            validation_config=validation_config,
            report=report,
            register_rejected_modules=(
                self.object_validator_validation_api is None
            )
        )

        # check whether request is done
        if len(validation_config.rejections) == 0 \
                and not modules_use_default:
            report.progress.numeric = 100
            report.log.log(
                Context.INFO,
                body=f"Target at '{target.path}' is "
                + ("valid." if report.data.valid else "invalid.")
            )
            push()
            return

        # does the api object exist (depends on
        # config.USE_OBJECT_VALIDATOR)
        if self.object_validator_validation_api is None:
            report.log.log(
                Context.WARNING,
                body="No Object Validator-service configured for modules."
            )
            report.log.log(
                Context.ERROR,
                body=[
                    rejection[1] for rejection in validation_config.rejections
                ]
            )
            report.progress.verbose = "completed validation"
            report.progress.numeric = 100
            push()
            return

        # forward remainder of request to Object Validator service
        report.progress.numeric = 50
        push()

        logid = "0@object_validator"
        external_report = self.validate_external(
            push=push, children=children,
            target=target,
            validation_config=validation_config,
            report=report,
            logid=logid,
            modules_use_default=modules_use_default,
            external_timeout=self.config.OBJECT_VALIDATOR_VALIDATION_TIMEOUT,
            api=self.object_validator_validation_api
        )

        report.progress.verbose = (
            f"processing validation result for '{target.path}'"
        )
        report.progress.numeric = 95
        push()

        if external_report is not None:
            report.data.valid = report.data.valid \
                and report.children[logid]["data"]["valid"]
            report.data.logid.append(logid)
            report.log.log(
                Context.INFO,
                body=f"Target at '{target.path}' is "
                + ("valid." if report.data.valid else "invalid.")
            )
            push()

    def validate_external(
        self,
        push, children: Children,
        target: Target,
        validation_config: ValidationConfig,
        report: ValidationReport,
        logid: str,
        modules_use_default: bool,
        external_timeout: int = 3600,
        api: Optional[dcm_object_validator_sdk.ValidationApi] = None
    ) -> Optional[dict]:
        """
        Job instructions for validating IP properties
        using an Object Validator service.

        Orchestration standard-arguments:
        push -- (orchestration-standard) push `data` to host process
        children -- (orchestration-standard) `ChildJob`-registry shared
                    via `push`

        Keyword arguments:
        target --  a `Target` object related to the request
        validation_config -- a `ValidationConfig`-config
        report -- `ValidationReport`-object associated with this `Job`
        logid -- id of the external log
        external_timeout -- timeout for external service
        modules_use_default -- if `True`, make the Object Validator-request
                            with `modules=None`, use rejections otherwise
        api -- Object Validator sdk API-object
        """

        report.progress.verbose = (
            f"submitting validation request for '{target.path}'"
        )
        push()

        # post request
        try:
            response = api.validate_ip({
                "validation": {
                    "target": {
                        "path": str(target.path)
                    },
                    "modules": None if modules_use_default else list(
                            map(lambda x: x[0], validation_config.rejections)
                        ),
                    "args": (
                        report.args["validation"].get("args", {})
                        if "validation" in report.args else {}
                    )
                }
            })
        except dcm_object_validator_sdk.rest.ApiException as exc_info:
            report.log.log(
                Context.ERROR,
                body=f"Job rejected by Object Validator: {exc_info.body} "
                + f"({exc_info.status})."
            )
            target.validation.valid = False
            return None
        except urllib3.exceptions.MaxRetryError:
            report.log.log(
                Context.ERROR,
                body="Object Validator-service unavailable."
            )
            target.validation.valid = False
            return None

        children.add(
            ChildJobEx(
                token=response.value,
                url=self.config.OBJECT_VALIDATOR_HOST,
                abort_path="/validate",
                id_=logid
            ),
            "Object Validator"
        )
        report.log.log(
            Context.INFO,
            body=f"Object Validator accepted submission: token={response.value}."
        )
        report.progress.verbose = (
            f"awaiting external validation of '{target.path}'"
        )
        push()
        # TODO: implement via callback
        # wait until finished (i.e. `get_report` returns a status != 503)
        if report.children is None:
            report.children = {}
        _elapsed = 0
        while True:
            sleep(0.25)
            # handle any API-exceptions
            try:
                external_report = \
                    api.get_report_with_http_info(
                        token=response.value
                    )
                if external_report.status_code == 200:
                    break
            except dcm_object_validator_sdk.rest.ApiException as exc_info:
                if exc_info.status == 503:
                    try:
                        report.children[logid] = json.loads(exc_info.data)
                    except json.JSONDecodeError:
                        pass
                    else:
                        push()
                else:
                    report.log.log(
                        Context.ERROR,
                        body=f"Object Validator returned with: {exc_info.body} "
                        + f"({exc_info.status})."
                    )
                    target.validation.valid = False
                    push()
                    raise exc_info
            if _elapsed/4 > external_timeout:
                report.log.log(
                    Context.ERROR,
                    body=f"Object Validator timed out after {_elapsed/4} seconds."
                )
                target.validation.valid = False
                report.children[logid] = {
                    "host": "object_validator",
                    "token": {
                        "value": response.value,
                        "expires": response.expires
                    } | (
                        {"expires_at": response.expires_at}
                        if response.expires else {}
                    ),
                    "args": report.args.get("validation", {}).get("args", {}),
                    "progress": {
                        "status": "aborted",
                        "verbose": "Aborted due to timeout.",
                        "numeric": 0
                    },
                    "log": {
                        Context.ERROR.name: [
                            LogMessage(
                                f"Service timed out after {_elapsed/4}s.",
                                origin="IP Builder"
                            ).json
                        ]
                    },
                    "data": {"valid": False}
                }
                children.remove("Object Validator")
                push()
                return report.children[logid]
            _elapsed = _elapsed + 1

        report.children[logid] = external_report.data.to_dict()
        children.remove("Object Validator")
        push()
        return report.children[logid]
