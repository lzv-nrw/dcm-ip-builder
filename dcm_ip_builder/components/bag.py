"""Custom Bag-class definition."""

from typing import Mapping
from pathlib import Path

import bagit_utils


class Bag(bagit_utils.Bag):
    """Customized `bagit_utils.Bag`."""

    def set_baginfo(
        self,
        baginfo: Mapping[str, str | list[str]],
        write_to_disk: bool = True,
    ) -> None:
        # map baginfo-values to lists where needed
        super().set_baginfo(
            {
                k: (v if isinstance(v, list) else [v])
                for k, v in baginfo.items()
            },
            write_to_disk,
        )

    def custom_validate_format_hook(self):
        report = bagit_utils.common.ValidationReport(True)

        # check for empty payload directory
        if (
            len(list(filter(Path.is_file, (self.path / "data").glob("**/*"))))
            == 0
        ):
            report.issues.append(
                bagit_utils.common.Issue("warning", "Bag contains no payload.")
            )

        return report
