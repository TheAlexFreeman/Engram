"""Read tools — search submodule."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_search(mcp: "FastMCP", get_repo, get_root, H) -> dict[str, object]:
    """Register search read tools and return their callables."""
    _IGNORED_NAMES = H._IGNORED_NAMES
    _display_rel_path = H._display_rel_path
    _is_humans_path = H._is_humans_path
    _resolve_humans_root = H._resolve_humans_root
    _resolve_visible_path = H._resolve_visible_path
    _tool_annotations = H._tool_annotations

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_search",
        annotations=_tool_annotations(
            title="Search Memory Files",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_search(
        query: str,
        path: str = ".",
        glob_pattern: str = "**/*.md",
        case_sensitive: bool = False,
        max_results: int = 30,
        context_lines: int = 0,
        include_humans: bool = False,
        freshness_weight: float = 0.0,
    ) -> str:
        """Search for a pattern across files in the memory repository.

        Uses git grep for tracked files (fast — git maintains an index), then
        falls back to a Python glob walk for any untracked files. Results are
        grouped by file with line numbers. When context_lines > 0, includes up
        to that many surrounding lines before and after each match. Context
        lines do not count toward max_results.

        When freshness_weight > 0, results are re-ranked by a combined score
        that blends match density with temporal freshness. Freshness is
        computed from ``last_verified`` (preferred) or ``created`` frontmatter
        dates using exponential decay (180-day half-life).

        Args:
            query:            Search string or Python regex (POSIX ERE via git grep).
            path:             Folder to search within (default: '.').
            glob_pattern:     File glob filter (default: '**/*.md').
            case_sensitive:   Case-sensitive match (default: False).
            max_results:      Max matching lines to return (default: 30, max 100).
            context_lines:    Number of surrounding lines to include before and
                              after each match (default: 0, max: 10).
            include_humans:   Include the human-facing HUMANS/ tree when searching
                              broad scopes like '.' (default: False).
            freshness_weight: Blend weight for temporal freshness (0.0–1.0).
                              0.0 = pure text order (default), 1.0 = pure recency.
                              When > 0, file groups are re-sorted by
                              ``(1 - freshness_weight) * text_score + freshness_weight * freshness``.

        Returns:
            Matching lines grouped by file with line numbers, or a not-found message.
        """
        from ...errors import StagingError, ValidationError

        root = get_root()
        search_root = _resolve_visible_path(root, path)
        if not search_root.exists():
            return f"Error: Path not found: {path}"

        if context_lines < 0:
            raise ValidationError("context_lines must be >= 0")
        if context_lines > 10:
            raise ValidationError("context_lines must be <= 10")

        freshness_weight = max(0.0, min(1.0, float(freshness_weight)))

        # Validate regex early so we can report a helpful error before spawning git
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            python_pattern = re.compile(query, flags)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        max_results = min(max_results, 100)
        explicit_humans_search = _is_humans_path(search_root, root)

        # Build the git-grep path prefix (repo-relative) so git restricts the search scope
        try:
            scope_prefix = search_root.relative_to(root).as_posix()
        except ValueError:
            scope_prefix = "."

        # Derive a simple glob extension for git grep from glob_pattern
        # e.g. "**/*.md" → "*.md"; "*.txt" → "*.txt"
        simple_glob = glob_pattern.lstrip("*/")  # strip leading **/ or */
        if not simple_glob:
            simple_glob = "*"

        # Build the path spec for git grep
        if scope_prefix in (".", ""):
            git_pathspec = simple_glob
        else:
            git_pathspec = f"{scope_prefix}/{simple_glob}"

        # Try git grep first (fast path for tracked files)
        repo = get_repo()
        if explicit_humans_search:
            raw_matches = None
        else:
            try:
                raw_matches = repo.grep(
                    query,
                    glob=git_pathspec,
                    case_sensitive=case_sensitive,
                )
            except StagingError:
                # git grep unavailable or failed — fall through to Python fallback
                raw_matches = None

        # Build per-file match groups from git grep output
        results: list[str] = []
        # Per-file groups: list of (file_rel, match_count, output_lines, suffix)
        file_groups: list[tuple[str, int, list[str], str]] = []
        total_matches = 0
        seen_files: set[str] = set()
        file_line_cache: dict[str, list[str]] = {}

        def _get_file_lines(file_rel: str, *, untracked_text: str | None = None) -> list[str]:
            if file_rel not in file_line_cache:
                if untracked_text is not None:
                    file_line_cache[file_rel] = untracked_text.splitlines()
                else:
                    try:
                        file_line_cache[file_rel] = (
                            (root / file_rel)
                            .read_text(encoding="utf-8", errors="replace")
                            .splitlines()
                        )
                    except OSError:
                        file_line_cache[file_rel] = []
            return file_line_cache[file_rel]

        def _append_match_lines(
            file_output: list[str],
            *,
            file_rel: str,
            line_no: int,
            line_text: str,
            untracked_text: str | None = None,
        ) -> None:
            cached_lines = _get_file_lines(file_rel, untracked_text=untracked_text)
            if not cached_lines:
                file_output.append(f"  {line_no}: {line_text.rstrip()}")
                return

            start_index = max(0, line_no - 1 - context_lines)
            end_index = min(len(cached_lines), line_no + context_lines)
            for current_index in range(start_index, end_index):
                rendered_line = cached_lines[current_index].rstrip()
                rendered_no = current_index + 1
                if rendered_no == line_no:
                    file_output.append(f"  {rendered_no}: {rendered_line}")
                else:
                    file_output.append(f"  {rendered_no}| {rendered_line}")

        if raw_matches is not None:
            # Group matches by file
            from itertools import groupby

            for file_rel, file_matches_iter in groupby(raw_matches, key=lambda t: t[0]):
                grouped_matches = list(file_matches_iter)
                file_path = root / file_rel

                # Apply HUMANS/ filter
                if (
                    not explicit_humans_search
                    and not include_humans
                    and _is_humans_path(file_path, root)
                ):
                    continue

                # Apply _IGNORED_NAMES filter
                if any(part in _IGNORED_NAMES for part in file_path.parts):
                    continue

                seen_files.add(file_rel)
                file_output: list[str] = []
                file_match_count = 0
                for _, line_no, line_text in grouped_matches:
                    _append_match_lines(
                        file_output,
                        file_rel=file_rel,
                        line_no=line_no,
                        line_text=line_text,
                    )
                    total_matches += 1
                    file_match_count += 1
                    if total_matches >= max_results:
                        break

                if file_output:
                    file_groups.append((file_rel, file_match_count, file_output, ""))

                if total_matches >= max_results:
                    break

        # Python fallback: search untracked files git grep wouldn't see
        if total_matches < max_results:
            for file_path in sorted(search_root.glob(glob_pattern)):
                if any(part in _IGNORED_NAMES for part in file_path.parts):
                    continue
                if not file_path.is_file():
                    continue
                try:
                    file_rel = _display_rel_path(file_path, root)
                except ValueError:
                    continue
                if file_rel in seen_files:
                    continue  # already handled by git grep
                if (
                    not explicit_humans_search
                    and not include_humans
                    and _is_humans_path(file_path, root)
                ):
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                cached_lines = _get_file_lines(file_rel, untracked_text=text)

                file_output = []
                file_match_count = 0
                for line_no, line in enumerate(cached_lines, 1):
                    if python_pattern.search(line):
                        _append_match_lines(
                            file_output,
                            file_rel=file_rel,
                            line_no=line_no,
                            line_text=line,
                            untracked_text=text,
                        )
                        total_matches += 1
                        file_match_count += 1
                        if total_matches >= max_results:
                            break

                if file_output:
                    file_groups.append((file_rel, file_match_count, file_output, " _(untracked)_"))

                if total_matches >= max_results:
                    break

        if (
            total_matches < max_results
            and not explicit_humans_search
            and include_humans
            and path in {"", "."}
        ):
            humans_root = _resolve_humans_root(root)
            if humans_root.exists() and humans_root.is_dir():
                for file_path in sorted(humans_root.glob(glob_pattern)):
                    if any(part in _IGNORED_NAMES for part in file_path.parts):
                        continue
                    if not file_path.is_file():
                        continue
                    file_rel = _display_rel_path(file_path, root)
                    if file_rel in seen_files:
                        continue
                    try:
                        text = file_path.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue

                    cached_lines = _get_file_lines(file_rel, untracked_text=text)

                    file_output = []
                    file_match_count = 0
                    for line_no, line in enumerate(cached_lines, 1):
                        if python_pattern.search(line):
                            _append_match_lines(
                                file_output,
                                file_rel=file_rel,
                                line_no=line_no,
                                line_text=line,
                                untracked_text=text,
                            )
                            total_matches += 1
                            file_match_count += 1
                            if total_matches >= max_results:
                                break

                    if file_output:
                        file_groups.append(
                            (file_rel, file_match_count, file_output, " _(untracked)_")
                        )

                    if total_matches >= max_results:
                        break

        if not file_groups:
            return f"No matches found for {query!r} in {path!r}."

        # --- Freshness re-ranking -------------------------------------------
        if freshness_weight > 0 and file_groups:
            from ...freshness import effective_date
            from ...freshness import freshness_score as _fs
            from ...frontmatter_utils import read_with_frontmatter

            max_matches = max(mc for _, mc, _, _ in file_groups)
            scored: list[tuple[float, float, int, str, int, list[str], str]] = []
            for idx, (frel, mc, lines, suffix) in enumerate(file_groups):
                text_score = mc / max_matches if max_matches else 0.0
                try:
                    fm_dict, _ = read_with_frontmatter(root / frel)
                    f_score = _fs(effective_date(fm_dict))
                except Exception:
                    f_score = 0.0
                combined = (1 - freshness_weight) * text_score + freshness_weight * f_score
                # Negate combined for descending sort; use idx for stable tie-break
                scored.append((-combined, f_score, idx, frel, mc, lines, suffix))
            scored.sort()

            results: list[str] = []
            truncated = total_matches >= max_results
            for neg_combined, f_score, _, frel, mc, lines, suffix in scored:
                header = f"\n**{frel}**{suffix}"
                if freshness_weight > 0:
                    header += f"  _(freshness: {f_score:.2f})_"
                results.append(header)
                results.extend(lines)
            if truncated:
                results.append(
                    f"\n_(truncated at {max_results} matches — use a narrower query or path)_"
                )
        else:
            results = []
            truncated = total_matches >= max_results
            for frel, mc, lines, suffix in file_groups:
                results.append(f"\n**{frel}**{suffix}")
                results.extend(lines)
            if truncated:
                results.append(
                    f"\n_(truncated at {max_results} matches — use a narrower query or path)_"
                )

        return "\n".join(results)

    # ------------------------------------------------------------------
    # memory_find_references

    return {
        "memory_search": memory_search,
    }
