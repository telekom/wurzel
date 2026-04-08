# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


def topological_node_ids(nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> list[str]:
    """Return node ``id`` values in an order that respects directed edges (source → target)."""
    ids = [n["id"] for n in nodes]
    id_set = set(ids)
    if len(id_set) != len(ids):
        raise ValueError("duplicate node id in DAG")

    adj: dict[str, list[str]] = defaultdict(list)
    indeg: dict[str, int] = dict.fromkeys(ids, 0)

    for e in edges:
        src, tgt = e["source"], e["target"]
        if src not in id_set or tgt not in id_set:
            raise ValueError(f"edge references unknown node: {src} -> {tgt}")
        adj[src].append(tgt)
        indeg[tgt] += 1

    q = deque([i for i in ids if indeg[i] == 0])
    out: list[str] = []
    while q:
        n = q.popleft()
        out.append(n)
        for v in adj[n]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)

    if len(out) != len(ids):
        raise ValueError("DAG has a cycle or disconnected nodes")
    return out
