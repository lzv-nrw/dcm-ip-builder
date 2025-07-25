"""
This module contains the definition of a bag_builder plugin
based on the bagit library, that can be used by the 'IP Builder'-app
to build IPs from IEs.
"""

from typing import Optional
from dataclasses import dataclass, field
from pathlib import Path
from shutil import copytree, rmtree, move
from tempfile import TemporaryDirectory

import bagit
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
    Implementation of a BagBuilder based on the BagIt library [1].

    [1] https://github.com/LibraryOfCongress/bagit-python
    """

    _NAME = "bagit_bag_builder"
    _DISPLAY_NAME = "BagIt Bag Builder"
    _DESCRIPTION = "Build Bags from IEs using the bagit library"
    _CONTEXT = "build"
    _DEPENDENCIES = [
        PythonDependency("bagit")
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
        ),
        encoding=Argument(
            type_=JSONType.STRING,
            required=False,
            default="utf-8",
            description="encoding for writing and reading manifest files "
            + "(see bagit library)",
            example="utf-8"
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

        # The bagit library does not support individual settings for manifests
        # and tag-manifests. This is, however, included in the DCM-
        # specification. Consequently, the union of both sets of algorithms is
        # used during bag-creation and unwanted files/entries in the tag-
        # manifests are removed afterwards
        # set the used algorithms as the union of manifests and tagmanifests
        self._checksums = list(set().union(self.manifests, self.tagmanifests))

    @classmethod
    def _validate_more(cls, kwargs):
        # ensure src is a directory
        if "src" in kwargs and not Path(kwargs["src"]).is_dir():
            return False, "'src' has to be a directory"
        return super()._validate_more(kwargs)

    def _call_bagit(
        self,
        context: BagItPluginContext,
        src: Path,
        encoding: str,
        bag_info: Optional[dict[str, str | list[str]]] = None,
    ) -> Optional[bagit.Bag]:
        """
        Make a bag from a directory.

        On success it returns a bagit.Bag-instance.
        If the basic bag validation fails, it returns None.

        This internal method uses the make_bag method from the bagit library.

        Keyword arguments:
        src -- path to an IE (containing "data" and optionally "meta")
        encoding -- encoding for writing and reading manifest files
                    (see bagit library)
        bag_info -- selected subset of metadata to be added to the
                    bag-info.txt; input is a dictionary with either strings
                    or lists of strings in its values
                    (default None)
        """

        context.set_progress(f"calling bagit on directory '{src}'")
        context.push()

        # Make the bag
        data_dir = src / "data"
        meta_dir = src / "meta"
        bag = bagit.make_bag(
            # bag_dir cannot be a Path object, due to the bagit library.
            bag_dir=str(data_dir),
            bag_info=bag_info,
            processes=1,
            checksums=self._checksums,
            checksum=None,
            encoding=encoding
        )

        # Override the file bagit.txt to set the BagIt-Version
        # This approach imitates the original creation of the file
        # in the bagit library
        # https://github.com/LibraryOfCongress/bagit-python/blob/ed81c2384955747e8ba9dcb9661df1ac1fd31222/bagit.py#L246
        bagit_file_path = Path(data_dir) / "bagit.txt"
        Path(bagit_file_path).write_text(
            (
                f"BagIt-Version: {self.info['bagit_version']}\n"
                f"Tag-File-Character-Encoding: {encoding.upper()}\n"
            ),
            encoding=encoding
        )
        # bag.version_info will be updated
        # after opening the Bag with bagit.Bag()
        # https://github.com/LibraryOfCongress/bagit-python/blob/ed81c2384955747e8ba9dcb9661df1ac1fd31222/bagit.py#L350C37-L350C37

        # Update the bag info
        # from bagit library: You can change the metadata
        # persisted to the bag-info.txt by using the info property on a Bag.
        bag = bagit.Bag(str(data_dir))
        # Generate the field Bagging-DateTime
        bag.info["Bagging-DateTime"] = now().astimezone().isoformat()
        # Delete the field Bagging-Date
        if "Bagging-Date" in bag.info:
            del bag.info["Bagging-Date"]
        # Save the bag without regenerating manifests
        bag.save(processes=1, manifests=False)

        if meta_dir.is_dir():
            # Add the metadata folder into the bag
            copytree(src=meta_dir, dst=data_dir / "meta")
            rmtree(meta_dir)
            # Save the bag and regenerate manifests
            # The save method from the bagit library recalculates
            # the Payload-Oxum (from the bag payload, i.e. all files/folders
            # in the data folder) and regenerates the manifest files
            # when manifests=True (in this step it is expected that the files
            # from the meta folder are added - which do NOT belong
            # in the bag payload).
            bag.save(processes=1, manifests=True)

        # Perform the basic validation routine from the bagit library
        if bag.is_valid(fast=False, completeness_only=False):
            return bag

        return None

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
        encoding: str,
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
        encoding -- encoding for writing and reading manifest files
                    (see bagit library)
        dest -- destination directory for the bag
                (default None; corresponds to building bag in-place)
        """

        # Report: write the input directory
        context.result.log.log(
            Context.INFO,
            body=f"Making bag from '{str(src)}'."
        )

        # Convert src into path.
        src = Path(src)

        # Validate the expected structure in src
        valid_ie, msg = self._validate_ie(src)
        if not valid_ie:
            context.result.log.log(
                Context.ERROR,
                body=msg
            )
            return

        # check whether output is valid
        if dest is not None:
            Path(dest).mkdir(exist_ok=exist_ok)
        # use temporary output as work-directory
        # tmp_dir is deleted when context manager is exited
        # use TMPDIR to explicitly set tmp-directory; see also
        # https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp
        with TemporaryDirectory() as tmp_dir:
            _dest = Path(tmp_dir)
            copytree(
                src, _dest, dirs_exist_ok=True
            )  # bagit works on copy of ie

            # Create the bag
            bag = self._call_bagit(
                context=context,
                src=_dest,
                bag_info=bag_info,
                encoding=encoding,
            )

            # remove the tmp-data and exit if a problem has occurred
            if bag is None:
                rmtree(_dest)
                context.result.log.log(
                    Context.ERROR,
                    body="Initial bag validation failed (bagit.Bag.is_valid "
                    + "returned False).",
                )
                return

            # move result to dest
            if dest is None:
                rmtree(src)
                bag_path = src
            else:
                rmtree(dest)
                bag_path = dest

            # using pathlib's 'rename' method (that uses os.rename)
            # does not support cross-filesystem/cross-device renaming, which
            # leads to an invalid cross-device link, when running in docker
            move(_dest / "data", bag_path)

        bag = bagit.Bag(str(bag_path))

        # Delete the manifest files that were not required
        for excessive_alg in set(self._checksums) - set(self.manifests):
            mfile = bag_path / Path("manifest-" + excessive_alg + ".txt")
            mfile.unlink()
        # Generate new tag-manifest files,
        # without generating new manifest files (-> manifests=False).
        bag.save(processes=1, manifests=False)
        # Delete the tag-manifest files that were not required
        for excessive_alg in set(self._checksums) - set(self.tagmanifests):
            tag_mfile = bag_path / Path(
                "tagmanifest-" + excessive_alg + ".txt"
            )
            tag_mfile.unlink()

        # Perform the basic validation routine from the bagit library
        if not bag.is_valid(fast=False, completeness_only=False):
            context.result.log.log(
                Context.ERROR,
                body="Secondary bag validation failed (bagit.Bag.is_valid "
                + "returned False).",
            )
            return

        # success
        context.result.log.log(Context.INFO, body="Successfully created bag.")

        context.result.path = bag_path
        context.result.success = True
        context.set_progress("success")
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
