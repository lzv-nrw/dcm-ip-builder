"""Mapping-plugin to base64-converter."""

from typing import Any
import sys
from pathlib import Path
import base64

try:
    import dill
except ImportError:
    print(
        "This script requires the dill-library, "
        + "install with 'pip install dill'.",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from dcm_ip_builder.plugins.mapping import GenericMapper, GenericUrlPlugin
except ImportError:
    print(
        "This script requires the dcm-ip-builder-library, "
        + "install with 'pip install .'.",
        file=sys.stderr,
    )
    sys.exit(1)


def print_help():
    """Print help-text and exit."""
    print(
        """This script converts python mapping-plugins to base64
compatible with the 'generic-mapper-plugin-base64'-plugin.

usage: python3 convert_mapper_to_base64.py [option]
Options (and corresponding environment variables):
-h,--help: print this message and exit
-i       : input file (see README.md for details)"""
    )
    sys.exit(0)


def get_file(args: list[str]):
    """Get file-path from call args"""
    try:
        return Path(args[args.index("-i") + 1])
    except IndexError:
        print("no input file specified", file=sys.stderr)
        sys.exit(1)


def import_mapper(file: Path) -> GenericMapper:
    """Dynamically import mapper from module-file."""
    if not file.is_file():
        print("bad input file", file=sys.stderr)
        sys.exit(1)

    class PluginLoader(GenericUrlPlugin):
        def load_plugin(self, file: Path) -> tuple[bool, str, Any]:
            return self._load_mapper(f"file://{file.resolve()}")

    success, msg, plugin = PluginLoader().load_plugin(file)
    if not success:
        print(f"unable to load plugin: {msg}", file=sys.stderr)
        sys.exit(1)
    return plugin


def convert_mapper(mapper: GenericMapper) -> bytes:
    """Serialize and encode in base64."""
    return base64.b64encode(dill.dumps(mapper))


if __name__ == "__main__":
    if len(sys.argv) == 1 or "-h" in sys.argv or "--help" in sys.argv:
        print_help()

    print(convert_mapper(import_mapper(get_file(sys.argv))))
