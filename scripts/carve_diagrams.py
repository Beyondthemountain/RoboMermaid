#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


VIEW_LINE_RE = re.compile(r"^\s*%%@view\s*:\s*(.+?)\s*$")
BEGIN_RE = re.compile(r"^\s*%%@begin\s*:\s*view\s*=\s*([A-Za-z0-9_.-]+)\s*$")
END_RE = re.compile(r"^\s*%%@end\s*$")

# Detect Mermaid "header" line (diagram type line). We treat it as global.
MERMAID_HEADER_PREFIXES = (
    "flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram",
    "stateDiagram-v2", "erDiagram", "journey", "gantt", "pie", "mindmap",
    "timeline", "requirementDiagram", "quadrantChart", "sankey-beta",
    "xychart-beta",
)

FRONTMATTER_DELIM_RE = re.compile(r"^\s*---\s*$")


def git_sha_short() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def strip_frontmatter(lines: List[str]) -> List[str]:
    """Remove leading YAML front-matter if present."""
    if not lines:
        return lines
    if not FRONTMATTER_DELIM_RE.match(lines[0]):
        return lines
    # find second ---
    for i in range(1, len(lines)):
        if FRONTMATTER_DELIM_RE.match(lines[i]):
            return lines[i + 1 :]
    return lines  # malformed; leave as-is


def is_global_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    # Mermaid init directive comes as %%{init: ...}%%, keep globally
    if s.startswith("%%{") and s.endswith("}%%"):
        return True
    # Any Mermaid diagram header should be global
    for p in MERMAID_HEADER_PREFIXES:
        if s.startswith(p + " ") or s == p:
            return True
    # Styles should be global by default
    if s.startswith("classDef ") or s.startswith("style ") or s.startswith("linkStyle "):
        return True
    return False


def parse_master(master_text: str) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Parse master .mmd and return:
      - global_lines: always included
      - view_to_lines: view-specific lines (already includes global lines later)
    """
    raw_lines = master_text.splitlines()
    lines = strip_frontmatter(raw_lines)

    global_lines: List[str] = []
    view_lines: Dict[str, List[str]] = {}

    pending_views: Optional[Set[str]] = None
    in_block: bool = False
    block_view: Optional[str] = None

    def add_to_views(vs: Set[str], ln: str) -> None:
        for v in vs:
            view_lines.setdefault(v, []).append(ln)

    for ln in lines:
        # Block handling
        m_begin = BEGIN_RE.match(ln)
        if m_begin and not in_block:
            in_block = True
            block_view = m_begin.group(1)
            # begin marker itself is not emitted
            continue

        if END_RE.match(ln) and in_block:
            in_block = False
            block_view = None
            continue

        # Line-level view tag
        m_view = VIEW_LINE_RE.match(ln)
        if m_view and not in_block:
            pending_views = {v.strip() for v in m_view.group(1).split(",") if v.strip()}
            continue

        # Decide where this line goes
        if in_block and block_view:
            add_to_views({block_view}, ln)
            continue

        if pending_views:
            add_to_views(pending_views, ln)
            pending_views = None
            continue

        # Untagged line: treat as global if it's "structural", otherwise also global (simplest rule)
        # This makes authoring easier: anything not tagged shows in all views.
        global_lines.append(ln)

    return global_lines, view_lines


def determine_views(view_lines: Dict[str, List[str]], explicit_views: Optional[List[str]]) -> List[str]:
    if explicit_views:
        return explicit_views
    return sorted(view_lines.keys())


def build_carved_mermaid(global_lines: List[str], per_view_lines: List[str]) -> str:
    # Ensure header/global lines come first, then view-specific lines.
    out: List[str] = []

    # Keep global lines in original order
    out.extend(global_lines)

    # Add view-specific lines, preserving order
    out.extend(per_view_lines)

    # Ensure trailing newline
    text = "\n".join(out).rstrip() + "\n"
    return text


def make_md_provenance(
    view: str,
    source_rel: str,
    version: str,
    generated: str,
    carved_mermaid: str,
    svg_rel: str,
) -> str:
    # Title is the view name, as requested.
    md = []
    md.append("---")
    md.append(f'title: "{view}"')
    md.append(f'source: "{source_rel}"')
    md.append(f'version: "{version}"')
    md.append(f'generated: "{generated}"')
    md.append("---")
    md.append("")
    md.append(f"# {view}")
    md.append("")
    md.append(f"[View SVG]({svg_rel})")
    md.append("")
    md.append("```mermaid")
    md.append(carved_mermaid.rstrip("\n"))
    md.append("```")
    md.append("")
    return "\n".join(md)


def render_svg(mmd_path: Path, svg_path: Path) -> None:
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    # Use npx with the local devDependency if present; -y avoids prompts.
    subprocess.check_call([
        "npx", "-y", "@mermaid-js/mermaid-cli",
        "-i", str(mmd_path),
        "-o", str(svg_path),
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description="Carve Mermaid master .mmd files into view-specific .md + .svg outputs.")
    ap.add_argument("--src", default="diagrams-src", help="Source directory containing master .mmd files")
    ap.add_argument("--out", default="diagrams", help="Output directory for carved files")
    ap.add_argument("--views", nargs="*", help="Optional explicit list of views to generate (otherwise inferred)")
    ap.add_argument("--no-render", action="store_true", help="Do not render SVGs (still writes .mmd and .md)")
    args = ap.parse_args()

    src_dir = Path(args.src)
    out_dir = Path(args.out)

    if not src_dir.exists():
        raise SystemExit(f"Source directory not found: {src_dir}")

    version = git_sha_short()
    generated = now_utc_iso()

    masters = sorted(src_dir.glob("*.mmd"))
    if not masters:
        print(f"No .mmd files found in {src_dir}")
        return 0

    for master in masters:
        master_text = master.read_text(encoding="utf-8")
        global_lines, view_to_lines = parse_master(master_text)
        views = determine_views(view_to_lines, args.views)

        base = master.stem  # e.g. UserJourneys

        # If no views found (no tags), you can still output a single "all" view
        if not views:
            views = ["all"]
            view_to_lines["all"] = []

        for view in views:
            carved = build_carved_mermaid(global_lines, view_to_lines.get(view, []))

            # Stable names
            mmd_name = f"{base}_{view}.mmd"
            svg_name = f"{base}_{view}.svg"
            md_name  = f"{base}_{view}.md"

            mmd_path = out_dir / mmd_name
            svg_path = out_dir / svg_name
            md_path  = out_dir / md_name

            out_dir.mkdir(parents=True, exist_ok=True)

            # Write carved Mermaid
            mmd_path.write_text(carved, encoding="utf-8")

            # Render SVG (no metadata in the image)
            if not args.no_render:
                render_svg(mmd_path, svg_path)

            # Write provenance MD (links to SVG)
            source_rel = str(master.as_posix())
            svg_rel = f"./{svg_name}"
            md_text = make_md_provenance(
                view=view,
                source_rel=source_rel,
                version=version,
                generated=generated,
                carved_mermaid=carved,
                svg_rel=svg_rel,
            )
            md_path.write_text(md_text, encoding="utf-8")

            print(f"Generated: {md_path} and {svg_path if not args.no_render else '(SVG skipped)'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
