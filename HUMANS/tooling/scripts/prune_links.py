"""Prune redundant cross-references from the densest knowledge base domains.

Run from the repo root:
    python HUMANS/tooling/scripts/prune_links.py
"""

import os
import re
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[3])
KB = os.path.join(_REPO_ROOT, "core", "memory", "knowledge")
DOMAINS = [
    "mathematics",
    "rationalist-community",
    "social-science",
    "ai",
    "software-engineering",
]
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*\.md[^)]*)\)")

total_removed = 0
files_modified = 0

for domain in DOMAINS:
    dpath = os.path.join(KB, domain)
    for root, dirs, files in os.walk(dpath):
        for f in files:
            if not f.endswith(".md") or f == "SUMMARY.md":
                continue
            fpath = os.path.join(root, f)
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read()

            # Split into frontmatter + body
            fm_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
            if not fm_match:
                continue
            frontmatter = content[: fm_match.end()]
            body = content[fm_match.end() :]

            # Split body into main content + Connections section
            conn_match = re.search(r"^(---\n\n)?## Connections\n", body, re.MULTILINE)
            if conn_match:
                main_body = body[: conn_match.start()]
                conn_section = body[conn_match.start() :]
            else:
                main_body = body
                conn_section = ""

            # Find all link targets in main body
            body_targets = set()
            for m in LINK_RE.finditer(main_body):
                body_targets.add(m.group(2))

            modified = False
            removed_count = 0

            # 1. Remove Connections entries that are already linked in body
            if conn_section and body_targets:
                new_conn_lines = []
                for line in conn_section.split("\n"):
                    link_match = LINK_RE.search(line)
                    if link_match and link_match.group(2) in body_targets:
                        removed_count += 1
                        modified = True
                        continue
                    new_conn_lines.append(line)
                conn_section = "\n".join(new_conn_lines)

            # 2. Deduplicate body links (keep first occurrence of each target)
            seen_in_body = set()
            new_main = []
            pos = 0
            for m in LINK_RE.finditer(main_body):
                target = m.group(2)
                if target in seen_in_body:
                    # Duplicate — convert to plain text
                    new_main.append(main_body[pos : m.start()])
                    new_main.append(m.group(1))  # Just link text
                    pos = m.end()
                    removed_count += 1
                    modified = True
                else:
                    seen_in_body.add(target)
                    new_main.append(main_body[pos : m.end()])
                    pos = m.end()
            new_main.append(main_body[pos:])
            main_body = "".join(new_main)

            # 3. Deduplicate within Connections section
            if conn_section:
                seen_conn = set()
                new_conn_lines = []
                for line in conn_section.split("\n"):
                    link_match = LINK_RE.search(line)
                    if link_match:
                        target = link_match.group(2)
                        if target in seen_conn:
                            removed_count += 1
                            modified = True
                            continue
                        seen_conn.add(target)
                    new_conn_lines.append(line)
                conn_section = "\n".join(new_conn_lines)

            # Clean up empty Connections section
            if conn_section:
                remaining = LINK_RE.findall(conn_section)
                if not remaining:
                    conn_section = ""
                    modified = True

            if modified:
                new_content = frontmatter + main_body + conn_section
                new_content = re.sub(r"\n{3,}", "\n\n", new_content)
                with open(fpath, "w", encoding="utf-8") as fh:
                    fh.write(new_content)
                relpath = os.path.relpath(fpath, KB).replace(os.sep, "/")
                print(f"  {relpath}: removed {removed_count} redundant links")
                total_removed += removed_count
                files_modified += 1

print(f"\nTotal: {total_removed} redundant links removed from {files_modified} files")
