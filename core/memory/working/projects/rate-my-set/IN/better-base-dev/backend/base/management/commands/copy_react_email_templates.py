from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Final

from django.conf import settings
from django.core.management.base import BaseCommand

BASE_DIR: Final[Path] = settings.BASE_DIR
APPS_DIR: Final[Path] = settings.APPS_DIR
REACT_EMAIL_DIR_BASE: Final[Path] = BASE_DIR / "emails" / "exported"
OUTPUT_DIR_BASE: Final[Path] = APPS_DIR / "templates" / "emails"

HANDLED_EXTENSIONS: Final[set[str]] = {".html", ".txt"}
STATIC_PREFIX: Final[str] = "{% static_for_email "
STATIC_REGEX: Final[re.Pattern] = re.compile(r"\{\% static_for_email (.+?) \%\}")
VARIABLES_SPACE_SANITIZATION_REGEX: Final[re.Pattern] = re.compile(
    r"\{\{(\s*)(\S+)(\s*)\}\}"
)


class Command(BaseCommand):
    """
    Copy generated `.html` and `.txt` files (generated `react-email` `.tsx` files and
    related) to the directory where they should live within a Django templates
    directory.
    """

    help = __doc__

    def handle(self, *args, **options):
        glob_patterns: list[str] = sorted(
            f"*.{ext.removeprefix('.')}" for ext in HANDLED_EXTENSIONS
        )
        paths: list[Path] = []
        for glob_pattern in glob_patterns:
            for path in REACT_EMAIL_DIR_BASE.rglob(glob_pattern):
                paths.append(path)

        for source in paths:
            self._copy_file(source)

        self.stdout.write(
            self.style.SUCCESS(
                f"{os.linesep}Successfully copied {len(paths)} files from "
                f"{REACT_EMAIL_DIR_BASE.relative_to(BASE_DIR)} to "
                f"{OUTPUT_DIR_BASE.relative_to(BASE_DIR)}."
            )
        )

    def _static_re_sub(self, match: re.Match) -> str:
        middle = (
            (match.group(1) or "").strip().removeprefix("&#x27;").removesuffix("&#x27;")
        )
        return f"{{% static_for_email '{middle}' %}}"

    def _variables_space_sanitization_re_sub(self, match: re.Match) -> str:
        return f"{{{{ {match.group(2)} }}}}"

    def _prepare_file(self, contents: str) -> str:
        has_static = STATIC_PREFIX in contents

        if not has_static:
            return VARIABLES_SPACE_SANITIZATION_REGEX.sub(
                self._variables_space_sanitization_re_sub, contents
            )

        transformed = STATIC_REGEX.sub(self._static_re_sub, contents)
        transformed = VARIABLES_SPACE_SANITIZATION_REGEX.sub(
            self._variables_space_sanitization_re_sub, transformed
        )
        transformed = f"{{% load static_for_email %}}\n{transformed}"
        if transformed.endswith("\n") or transformed.endswith(os.linesep):
            return transformed
        return f"{transformed}\n"

    def _copy_file(self, source: Path) -> Path:
        output_sub_path = Path(
            os.sep.join(source.relative_to(REACT_EMAIL_DIR_BASE).parts[1:])
        )
        destination = OUTPUT_DIR_BASE / output_sub_path
        destination.parent.mkdir(parents=True, exist_ok=True)

        with open(source, encoding="utf-8") as f:
            read_value = f.read()

        final_contents = self._prepare_file(read_value)

        with open(destination, "w", encoding="utf-8") as f:
            f.write(final_contents)

        self.stdout.write(
            self.style.SUCCESS(
                f"{source.relative_to(REACT_EMAIL_DIR_BASE)}"
                " --> "
                f"{destination.relative_to(OUTPUT_DIR_BASE)}"
                f" ({len(final_contents)})"
            )
        )

        return destination
