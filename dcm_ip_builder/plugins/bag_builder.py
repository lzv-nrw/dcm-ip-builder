"""
This module contains the definition of a bag_builder plugin.
"""

from typing import Optional
from dataclasses import dataclass, field
from pathlib import Path
from shutil import rmtree, move
from tempfile import TemporaryDirectory

import bagit_utils
from dcm_common.plugins import (
    Signature,
    PluginResult,
    PluginInterface,
    FSPlugin,
    Argument, JSONType,
    PythonDependency,
    PluginExecutionContext
)
from dcm_common.logger import LoggingContext as Context
from dcm_common.util import now, list_directory_content
from dcm_common.models import DataModel

from dcm_ip_builder.components import Bag


@dataclass
class BagItPluginResult(PluginResult):
    """Data model for the result of BagItBagBuilder-Plugin."""

    path: Optional[Path] = None
    success: Optional[bool] = None

    @DataModel.serialization_handler("path")
    @classmethod
    def path_serialization_handler(cls, value):
        """Performs `path`-serialization."""
        if value is None:
            DataModel.skip()
        return str(value)

    @DataModel.deserialization_handler("path")
    @classmethod
    def path_deserialization(cls, value):
        """Performs `path`-deserialization."""
        if value is None:
            DataModel.skip()
        return Path(value)


@dataclass
class BagItPluginContext(PluginExecutionContext):
    """
    Data model for the execution context of `DemoPlugin`-invocations.
    """

    result: BagItPluginResult = field(default_factory=BagItPluginResult)


@dataclass
class InfoModel(DataModel):
    """info model"""

    bagit_version: str


class BagItBagBuilder(PluginInterface, FSPlugin):
    """
    Implementation of a BagBuilder based on the bagit-utils library [1].

    [1] https://github.com/RichtersFinger/bagit-utils
    """

    _NAME = "bagit-bag-builder"
    _DISPLAY_NAME = "BagIt-Bag-Builder-Plugin"
    _DESCRIPTION = "Build Bags from IEs using the bagit-utils library"
    _CONTEXT = "build"
    _DEPENDENCIES = [
        PythonDependency("bagit-utils")
    ]
    _SIGNATURE = Signature(
        src=Argument(
            type_=JSONType.STRING,
            required=True,
            description="path to the source directory of the IE",
            example="relative/path/to/directory"
        ),
        bag_info=Argument(
            type_=JSONType.OBJECT,
            required=True,
            additional_properties=True,
            description="selected subset of metadata to be added to the "
            + "bag-info.txt; input is a dictionary with either strings "
            + "or lists of strings in its values",
            example={
                "author": ["Author 1", "Author 2"],
                "title": "Some title"
            }
        ),
        dest=Argument(
            type_=JSONType.STRING,
            required=False,
            default=None,
            description="destination directory for the bag "
            + "(default None; corresponds to building bag in-place)",
            example="relative/path/to/directory"
        ),
        exist_ok=Argument(
            type_=JSONType.BOOLEAN,
            required=False,
            default=False,
            description="if `False` and `dest` is not `None` and already "
            + "exists, a `FileExistsError` is raised",
            example=True
        )
    )
    _RESULT_TYPE = BagItPluginResult
    _INFO = InfoModel(bagit_version="1.0")

    def __init__(
        self,
        manifests: list[str],
        tagmanifests: list[str],
        **kwargs
    ) -> None:
        """
        Keyword arguments:
        manifests -- list with the algorithms to be used for
                     the manifest files when creating bags.
        tagmanifests -- list with the algorithms to be used for
                        the tag-manifest files when creating bags.
        """

        super().__init__(**kwargs)

        self.manifests = manifests
        self.tagmanifests = tagmanifests

    @classmethod
    def _validate_more(cls, kwargs):
        # ensure src is a directory
        if "src" in kwargs and not Path(kwargs["src"]).is_dir():
            return False, "'src' has to be a directory"
        return super()._validate_more(kwargs)

    def _validate_ie(self, src: Path) -> tuple[bool, str]:
        """Validate src-directory structure/contents."""
        if not (src / "data").is_dir():
            return False, (
                "Source IE does not follow specification. "
                + "Missing 'data' directory."
            )
        bad_contents = [
            str(p) for p in list_directory_content(
                src,
                pattern="*",
                condition_function=lambda p:
                    p not in ((src / "data"), (src / "meta"))
            )
        ]
        if bad_contents:
            return False, (
                "Source IE does not follow specification. "
                + f"Problematic content: {bad_contents}."
            )
        return True, ""

    def _make_bag(
        self,
        context: BagItPluginContext,
        src: str,
        bag_info: dict[str, str | list[str]],
        exist_ok: bool,
        dest: Optional[str] = None
    ) -> None:
        """
        Makes a bag from an intellectual entity (IE). Returns this bag
        on success, otherwise returns `None`.

        It expects an IE structure that conforms to the LZV.nrw
        specifications:
        INPUT
        <src>/
            ├── data/
            └── meta/ (optional)
        OUTPUT
        <output_path>/ (or <src>/)
            ├── data/
            ├── meta/ (optional)
            ├── bag-info.txt
            ├── bagit.txt
            ├── manifest-<checksum_abbreviation>.txt (multiple txt files)
            └── tagmanifest-<checksum_abbreviation>.txt (multiple txt files)

        Keyword arguments:
        src -- path to the source directory of the IE
        bag_info -- selected subset of metadata to be added to the
                    bag-info.txt; input is a dictionary with either strings
                    or lists of strings in its values
        exist_ok -- if `False` and `dest` is not `None` and already
                    exists, a `FileExistsError` is raised
        dest -- destination directory for the bag
                (default None; corresponds to building bag in-place)
        """

        # Report: write the input directory
        context.result.log.log(
            Context.INFO,
            body=f"Making bag from '{str(src)}'."
        )
        context.push()

        # Convert src/dest into paths.
        src = Path(src)
        if dest is not None:
            dest = Path(dest)

        # Validate the expected structure in src
        valid_ie, msg = self._validate_ie(src)
        if not valid_ie:
            context.result.log.log(
                Context.ERROR,
                body=msg
            )
            context.push()
            return

        # check whether output is valid
        if dest is not None:
            dest.mkdir(parents=True, exist_ok=exist_ok)

        # use temporary output as work-directory
        # tmp_dir is deleted when context manager is exited
        # use TMPDIR to explicitly set tmp-directory; see also
        # https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp
        with TemporaryDirectory() as tmp_dir:
            _dest = Path(tmp_dir)

            # build bag (without manifests since this method does not
            # support separate sets of algorithms for manifests and
            # tag-manifests)
            try:
                bag = Bag.build_from(
                    src=src,
                    dst=_dest,
                    baginfo=bag_info
                    | {
                        "Bagging-DateTime": [
                            now().isoformat(),
                        ],
                        "Payload-Oxum": [
                            Bag.get_payload_oxum(src / "data")
                        ],
                    },
                    algorithms=[],
                    validate=False,
                )
            except bagit_utils.BagItError as exc_info:
                context.result.log.log(
                    Context.ERROR,
                    body=f"Error while building Bag from '{src}': {exc_info}",
                )
                context.push()
                rmtree(_dest)
                return

            # generate manifests
            bag.set_manifests(self.manifests)
            bag.set_tag_manifests(self.tagmanifests)

            # move result to dest
            if dest is None:
                rmtree(src)
                bag.path = src
            else:
                rmtree(dest)
                bag.path = dest

            # using pathlib's 'rename' method (that uses os.rename)
            # does not support cross-filesystem/cross-device renaming, which
            # leads to an invalid cross-device link, when running in docker
            move(_dest, bag.path)

        # run validation of bag-format
        report = bag.validate_format()
        for issue in report.issues:
            match issue.level:
                case "error":
                    issue_context = Context.ERROR
                case "warning":
                    issue_context = Context.WARNING
                case _:
                    issue_context = Context.INFO
            context.result.log.log(
                issue_context, body=issue.message
            )

        if report.valid:
            context.result.log.log(
                Context.INFO, body=f"Successfully created bag at '{bag.path}'."
            )
            context.set_progress("success")
        else:
            context.result.log.log(
                Context.INFO,
                body=f"Bag creation resulted in invalid bag at '{bag.path}'.",
            )
            context.set_progress("failure")

        context.result.path = bag.path
        context.result.success = report.valid
        context.push()

    def _get(
        self, context: BagItPluginContext, /, **kwargs
    ) -> BagItPluginResult:

        # validate whether request is ok
        valid, msg = self.validate(kwargs)
        if not valid:
            context.result.log.log(
                Context.ERROR,
                body=f"Invalid request: {msg}",
            )
            context.result.success = False
            return context.result

        self._make_bag(context, **kwargs)

        # failure
        if Context.ERROR in context.result.log.keys():
            context.result.log.log(
                Context.INFO,
                body="Failed to create bag."
            )
            context.result.path = None
            context.result.success = False
            context.set_progress("failure")
            context.push()

        return context.result

    def get(  # this simply narrows down the involved types
        self, context: Optional[BagItPluginContext], /, **kwargs
    ) -> BagItPluginResult:
        return super().get(context, **kwargs)
