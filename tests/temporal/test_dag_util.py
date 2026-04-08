# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.temporal_worker.dag_util import topological_node_ids


def test_topological_order_linear():
    nodes = [{"id": "a"}, {"id": "b"}]
    edges = [{"source": "a", "target": "b"}]
    assert topological_node_ids(nodes, edges) == ["a", "b"]


def test_cycle_raises():
    nodes = [{"id": "a"}, {"id": "b"}]
    edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]
    with pytest.raises(ValueError, match="cycle|disconnected"):
        topological_node_ids(nodes, edges)
