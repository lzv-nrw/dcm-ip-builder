"""
Utility definitions usable by mapping-plugins.
"""

from typing import Optional, Callable
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


def load_xml_tree_from_file(path: Path) -> ElementTree.ElementTree:
    """Load XML-metadata from file at `path` as `ElementTree`."""
    return ElementTree.fromstring(path.read_text(encoding="utf-8"))


@dataclass
class XMLMappingRule:
    """XML-mapping rule."""

    src: Iterable[str]
    dst: str
    ns: Optional[dict[str, str]] = None
    reduce: Callable[[ElementTree.ElementTree], str] = lambda x: x.text
    post_process: Callable[[list[str]], list[str]] = lambda x: x

    @classmethod
    def _get_elements(
        cls,
        tree: Optional[
            ElementTree.ElementTree | list[ElementTree.ElementTree]
        ],
        path: Iterable[str],
        ns: Optional[dict[str, str]] = None,
    ) -> list[ElementTree.ElementTree]:
        """
        Get element at `path` in `tree` using the ElementTree XML API.

        If the path does not exist, returns an empty list.
        """
        if not path:
            return tree
        if tree is None:
            return None
        if isinstance(tree, list):
            return sum(
                (
                    cls._get_elements(e.findall(path[0], ns), path[1:], ns)
                    for e in tree
                    if e is not None
                ),
                start=[],
            )
        return cls._get_elements(tree.findall(path[0], ns), path[1:], ns)

    def map(
        self,
        tree: ElementTree.ElementTree,
    ) -> list[str]:
        """
        Execute mapping rule on the given `tree`.

        Keyword arguments:
        tree -- XML-tree
        """
        return self.post_process(
            list(map(self.reduce, self._get_elements(tree, self.src, self.ns)))
        )


@dataclass
class XMLXPathMappingRule:
    """XML-Mapping rule using XPath."""

    src: str
    dst: str
    ns: Optional[dict[str, str]] = None
    reduce: Callable[[ElementTree.ElementTree], str] = lambda x: x.text
    post_process: Callable[[list[str]], list[str]] = lambda x: x

    @staticmethod
    def _get_elements(
        tree: ElementTree.ElementTree,
        xpath: str,
        ns: Optional[dict[str, str]] = None,
    ) -> list[ElementTree.ElementTree]:
        """
        Get element at `xpath` in `tree` using the ElementTree XML API.

        If the path does not exist, returns an empty list.
        """
        return tree.findall(xpath, ns)

    def map(
        self,
        tree: ElementTree.ElementTree,
    ) -> list[str]:
        """
        Execute mapping rule on the given `tree`.

        Keyword arguments:
        tree -- XML-tree
        """
        return self.post_process(
            list(map(self.reduce, self._get_elements(tree, self.src, self.ns)))
        )
