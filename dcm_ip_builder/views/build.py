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
from dcm_common.models.report import Status
from dcm_common.orchestration import JobConfig, Job, Children
from dcm_common import services
from dcm_object_validator.views.validation \
    import validate as validate_native
from dcm_object_validator.models import ValidationConfig
from dcm_object_validator.models.validation_modules \
    import complete_validator_kwargs
import dcm_object_validator_sdk
from dcm_bag_builder import builder

from dcm_ip_builder.config import AppConfig
from dcm_ip_builder.models.build_config import _BuildConfig
from dcm_ip_builder.models import BuildConfig, BuildReport, Target
from dcm_ip_builder.views.validation import ValidationView
from dcm_ip_builder.handlers import get_build_handler, MapperConverterConfig


class BuildView(services.OrchestratedView):
    """View-class for ip-building."""

    NAME = "ip-build"

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

        self.validation_view = ValidationView(self.config)

        # initialize bag builder
        self.bag_builder = builder.BagBuilder(
            manifests=self.config.MANIFESTS,
            tagmanifests=self.config.TAG_MANIFESTS
        )

    def configure_bp(self, bp: Blueprint, *args, **kwargs) -> None:
        @bp.route("/build", methods=["POST"])
        @flask_handler(  # unknown query
            handler=services.no_args_handler,
            json=flask_args,
        )
        @flask_handler(  # process ip-build
            handler=get_build_handler(
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
        def build(
            build: _BuildConfig,
            validation: dict,
            callback_url: Optional[str] = None
        ):
            """Submit IE for IP building."""

            token = self.orchestrator.submit(
                JobConfig(
                    request_body={
                        "build": build.json,
                        "validation": validation,
                        "callback_url": callback_url
                    },
                    context=self.NAME
                )
            )
            return jsonify(token.json), 201

        self._register_abort_job(bp, "/build")

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
        # deserialize config
        build_config, _, _ = MapperConverterConfig.try_loading_config(
            config_str=config.request_body["build"]["config"],
            loc=".build.configuration"
        )
        return Job(
            cmd=lambda push, data, children: self.build(
                push, data, children,
                build_config=BuildConfig(
                    target=Target.from_json(
                        config.request_body["build"]["target"]
                    ),
                    config=build_config,
                    bagit_profile_url=(
                        config.request_body["build"]["bagit_profile_url"]
                    ),
                    payload_profile_url=(
                        config.request_body["build"]["payload_profile_url"]
                    ),
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

    def build(
        self, push, report, children: Children,
        build_config: BuildConfig,
        validation_config: ValidationConfig,
        modules_use_default: bool
    ):
        """
        Job instructions for the '/build' endpoint.

        Contains the following steps:
        * building IP
        * native validation (if required)
        * external validation (if required)

        Orchestration standard-arguments:
        push -- (orchestration-standard) push `report` to host process
        report -- (orchestration-standard) common report-object shared
                  via `push`
        children -- (orchestration-standard) `ChildJob`-registry shared
                    via `push`

        Keyword arguments:
        validation_config -- a `ValidationConfig`-config
        modules_use_default -- if `True`, make the Object Validator-request
                               with `modules=None`, use rejections otherwise
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
            report.data.valid = False
            report.data.validation.valid = False
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
        bag_info = self.get_baginfo(build_config, self.config)
        if len(bag_info) == 0:
            report.log.log(
                Context.WARNING,
                body="Empty bag-info metadata (missing 'source_metadata.xml'"
                + " in target?)."
            )
            push()

        # Build IP
        IP = self.bag_builder.make_bag(
            src=build_config.target.path,
            bag_info=bag_info,
            dest=report.data.path,
            exist_ok=True
        )
        report.log.merge(
            self.bag_builder.log.pick(Context.INFO, complement=True)
        )
        push()

        # exit if building failed
        if IP is None:
            report.data.valid = False
            report.data.validation.valid = False
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

        # regarding bag-builder, the result is valid (modify value below
        # based on proper validation)
        valid = True
        report.log.log(
            Context.INFO,
            body="Successfully assembled IP at "
            + f"'{report.data.path}'."
        )
        push()

        # exit if app is configured to not perform validation
        if not self.config.DO_VALIDATION:
            report.data.valid = False
            report.data.validation.valid = False
            if len(validation_config.modules) != 0:
                report.log.log(
                    Context.ERROR,
                    body="App is configured to skip validation but modules-arg"
                    + " is not empty."
                )
                push()
            return

        # define validation target
        validation_target = Target(path=report.data.path)

        if len(validation_config.modules) > 0:
            # perform native validation
            native_report = validate_native(
                push=push,
                target=validation_target,
                validation_config=validation_config,
                report=BuildReport(
                    host=report.host,
                    token=report.token,
                    args={
                        "validation": report.args.get("validation", {})
                    },
                    progress=report.progress,
                    data=validation_target.validation
                ),
                register_rejected_modules=(
                    self.object_validator_validation_api is None
                )
            )
            if native_report is not None:
                logid = "0@native"
                native_report["progress"]["verbose"] = (
                    "shutting down after success"
                )
                native_report["progress"]["numeric"] = 100
                native_report["progress"]["status"] = Status.COMPLETED.value
                report.children = {}
                report.children[logid] = native_report
                valid = (
                    valid and report.children[logid]["data"]["valid"]
                )
                report.data.logid.append(logid)
                push()

        # check whether request is done
        if len(validation_config.rejections) == 0 \
                and not modules_use_default:
            report.data.valid = valid
            report.log.log(
                Context.INFO,
                body=f"IP at '{report.data.path}' is "
                + ("valid." if report.data.valid else "invalid.")
            )
            push()
            return

        # does the api object exist (depends on config.USE_OBJECT_VALIDATOR)
        if self.object_validator_validation_api is None:
            report.log.log(
                Context.WARNING,
                body="No Object Validator-service configured, but unknown/"
                + "unsupported modules remain: "
                + str([r[0] for r in validation_config.rejections])
            )
            report.log.log(
                Context.ERROR,
                origin="Module Selector",
                body=[r[1] for r in validation_config.rejections]
            )
            report.data.validation.valid = \
                len(validation_config.rejections) == 0
            push()
            return

        # forward remainder of request to Object Validator service
        logid = "1@object_validator"
        external_report = self.validation_view.validate_external(
            push=push, children=children,
            target=validation_target,
            validation_config=validation_config,
            report=report,
            logid=logid,
            modules_use_default=modules_use_default,
            external_timeout=self.config.OBJECT_VALIDATOR_VALIDATION_TIMEOUT,
            api=self.object_validator_validation_api
        )

        report.progress.verbose = (
            f"processing validation result for '{validation_target.path}'"
        )
        push()

        if external_report is not None:
            report.data.logid.append(logid)
            report.data.valid = valid \
                and report.children[logid]["data"]["valid"]
            report.log.log(
                Context.INFO,
                body=f"IP at '{report.data.path}' is "
                + ("valid." if report.data.valid else "invalid.")
            )
            push()
            return

        report.data.valid = False
        report.log.log(
                Context.ERROR,
                body="Cannot connect to Object Validator service at "
                + f"'{self.config.OBJECT_VALIDATOR_HOST}'."
            )
        push()

    def get_baginfo(
        self,
        build_config: BuildConfig,
        app_config: AppConfig
    ) -> dict:
        """
        Returns dict of baginfo-metadata.

        Keyword arguments:
        build_config -- request's `BuildConfig`
        app_config -- app's `AppConfig`
        """

        # Generate metadata-subset for bag-info.txt
        # Convert source to dict
        metadata_filepath = build_config.target.path \
            / app_config.META_DIRECTORY \
            / app_config.SOURCE_METADATA
        if not metadata_filepath.is_file():
            return {}
        source_dict = build_config.config.CONVERTER().get_dict(
            metadata_filepath.read_text("utf-8")
        )
        # Map metadata
        bag_info = {}
        for key in app_config.MAPPED_METADATA_FIELDS:
            value = build_config.config.MAPPER().get_metadata(
                key,
                source_dict
            )
            if value is not None:
                bag_info[key] = value
        # Provide additional information for bag-info
        bag_info["Bag-Software-Agent"] = \
            "dcm-ip-builder v" + version("dcm-ip-builder")
        bag_info["BagIt-Profile-Identifier"] = \
            build_config.bagit_profile_url
        bag_info["BagIt-Payload-Profile-Identifier"] = \
            build_config.payload_profile_url
        return bag_info

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
