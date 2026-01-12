#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import yaml  # pip install pyyaml


def safe_id(s: str) -> str:
    out = []
    for ch in s:
        out.append(ch.lower() if ch.isalnum() else "_")
    # collapse underscores
    cleaned = []
    prev = ""
    for ch in out:
        if ch == "_" and prev == "_":
            continue
        cleaned.append(ch)
        prev = ch
    return "".join(cleaned).strip("_") or "node"


def load_model(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def tags_of(obj: Dict[str, Any]) -> Set[str]:
    return set(obj.get("tags") or [])


def build_adjacency(edges: List[Dict[str, Any]]) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    out_adj: Dict[str, Set[str]] = defaultdict(set)
    in_adj: Dict[str, Set[str]] = defaultdict(set)
    for e in edges:
        s, t = e["from"], e["to"]
        out_adj[s].add(t)
        in_adj[t].add(s)
    return out_adj, in_adj


def expand_neighbours(
    seed: Set[str],
    out_adj: Dict[str, Set[str]],
    in_adj: Dict[str, Set[str]],
    k: int,
) -> Set[str]:
    if k <= 0:
        return set(seed)
    seen = set(seed)
    q = deque([(n, 0) for n in seed])
    while q:
        n, d = q.popleft()
        if d == k:
            continue
        for nb in out_adj.get(n, set()) | in_adj.get(n, set()):
            if nb not in seen:
                seen.add(nb)
                q.append((nb, d + 1))
    return seen


def expand_directional(
    seed: Set[str],
    out_adj: Dict[str, Set[str]],
    in_adj: Dict[str, Set[str]],
    outbound: int = 0,
    inbound: int = 0,
) -> Set[str]:
    seen = set(seed)

    def walk(adj: Dict[str, Set[str]], depth: int) -> None:
        if depth <= 0:
            return
        q = deque([(n, 0) for n in seed])
        while q:
            n, d = q.popleft()
            if d == depth:
                continue
            for nb in adj.get(n, set()):
                if nb not in seen:
                    seen.add(nb)
                    q.append((nb, d + 1))

    walk(out_adj, outbound)
    walk(in_adj, inbound)
    return seen


def select_for_view(
    view: Dict[str, Any],
    nodes: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    out_adj: Dict[str, Set[str]],
    in_adj: Dict[str, Set[str]],
) -> Tuple[Set[str], Set[Tuple[str, str]]]:
    include = view.get("include") or {}
    expand = view.get("expand") or {}

    include_nodes: Set[str] = set()

    # 1) Explicit nodes
    include_nodes |= set(include.get("nodes") or [])

    # 2) Nodes by tag
    include_tags = set(include.get("tags") or [])
    if include_tags:
        for nid, meta in nodes.items():
            if include_tags & tags_of(meta):
                include_nodes.add(nid)

    # 3) Edges by tag (and auto-include endpoints)
    include_edge_tags = set(include.get("edge_tags") or [])
    include_edges: Set[Tuple[str, str]] = set()

    def edge_matches(e: Dict[str, Any]) -> bool:
        if not include_edge_tags:
            return False
        return bool(include_edge_tags & tags_of(e))

    for e in edges:
        s, t = e["from"], e["to"]
        if edge_matches(e):
            include_edges.add((s, t))
            include_nodes.add(s)
            include_nodes.add(t)

    # If no selectors specified, default to everything (sensible fallback)
    if not include_nodes and not include_edges:
        include_nodes = set(nodes.keys())
        include_edges = {(e["from"], e["to"]) for e in edges}

    # Expansion options
    if "neighbours" in expand:
        include_nodes = expand_neighbours(include_nodes, out_adj, in_adj, int(expand["neighbours"]))

    if "outbound" in expand or "inbound" in expand:
        include_nodes = expand_directional(
            include_nodes, out_adj, in_adj,
            outbound=int(expand.get("outbound") or 0),
            inbound=int(expand.get("inbound") or 0),
        )

    # If edges weren’t explicitly selected, include edges between included nodes
    if not include_edges:
        for e in edges:
            s, t = e["from"], e["to"]
            if s in include_nodes and t in include_nodes:
                include_edges.add((s, t))

    # Keep only valid nodes
    include_nodes = {n for n in include_nodes if n in nodes}

    return include_nodes, include_edges


def mermaid_node(nid: str, meta: Dict[str, Any]) -> str:
    label = meta.get("label", nid)
    kind = (meta.get("kind") or "service").lower()
    mid = safe_id(nid)

    if kind in {"database", "db"}:
        return f'  {mid}[("{label}")]'
    if kind in {"queue", "bus", "topic"}:
        return f'  {mid}(["{label}"])'
    return f'  {mid}["{label}"]'


def render_mermaid(
    title: str,
    layout: str,
    nodes: Dict[str, Dict[str, Any]],
    included_nodes: Set[str],
    included_edges: Set[Tuple[str, str]],
) -> str:
    lines: List[str] = []

    # Front-matter (YAML)
    lines.append("---")
    lines.append(f"title: {title}")
    lines.append("---")

#    lines.append(f"flowchart {layout}")
#    lines.append(f"  title {title}")
    
    lines.append(f"flowchart {layout}")
    lines.append("")

    for nid in sorted(included_nodes):
        lines.append(mermaid_node(nid, nodes[nid]))

    lines.append("")
    for s, t in sorted(included_edges, key=lambda x: (x[0], x[1])):
        if s in included_nodes and t in included_nodes:
            lines.append(f"  {safe_id(s)} --> {safe_id(t)}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/system.yaml")
    ap.add_argument("--out", default="diagrams")
    args = ap.parse_args()

    model = load_model(Path(args.model))
    system_name = (model.get("system") or {}).get("name", "System")
    nodes: Dict[str, Dict[str, Any]] = model.get("nodes") or {}
    edges: List[Dict[str, Any]] = model.get("edges") or []
    views: Dict[str, Dict[str, Any]] = model.get("views") or {}

    out_adj, in_adj = build_adjacency(edges)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate one file per view
    for view_name, view in views.items():
        title = view.get("title") or f"{system_name} — {view_name}"
        layout = view.get("layout") or "LR"

        inc_nodes, inc_edges = select_for_view(view, nodes, edges, out_adj, in_adj)
        mmd = render_mermaid(title, layout, nodes, inc_nodes, inc_edges)

        (out_dir / f"{view_name}.mmd").write_text(mmd, encoding="utf-8")

    print(f"Generated {len(views)} Mermaid files in {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
