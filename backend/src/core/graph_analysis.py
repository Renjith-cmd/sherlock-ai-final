"""Graph topological analysis: shortest path, degrees, connected components, and metrics."""

from collections import deque
from typing import List, Dict, Any, Optional, Set
from src.core.models import Entity, Relationship


class GraphAnalyzer:
    def __init__(self, entities: List[Entity], relationships: List[Relationship]):
        self.entities = entities
        self.relationships = relationships
        self.adj: Dict[str, Set[str]] = {e.id: set() for e in entities}
        self.in_degree: Dict[str, int] = {e.id: 0 for e in entities}
        self.out_degree: Dict[str, int] = {e.id: 0 for e in entities}

        for r in relationships:
            if r.source_id in self.adj and r.target_id in self.adj:
                self.adj[r.source_id].add(r.target_id)
                self.adj[r.target_id].add(r.source_id)  # Undirected for connectivity
                self.out_degree[r.source_id] += 1
                self.in_degree[r.target_id] += 1

    def compute_metrics(self) -> Dict[str, Any]:
        """Compute basic graph statistics and degree centrality."""
        node_count = len(self.entities)
        edge_count = len(self.relationships)

        degrees = {
            e.id: {
                "in_degree": self.in_degree[e.id],
                "out_degree": self.out_degree[e.id],
                "total_degree": self.in_degree[e.id] + self.out_degree[e.id]
            }
            for e in self.entities
        }

        # Calculate high centrality nodes
        top_hubs = sorted(
            self.entities,
            key=lambda e: degrees[e.id]["total_degree"],
            reverse=True
        )[:5]

        components = self.get_connected_components()

        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "connected_components_count": len(components),
            "degrees": degrees,
            "top_hubs": [
                {"id": h.id, "label": h.label, "type": h.type, "degree": degrees[h.id]["total_degree"]}
                for h in top_hubs
            ]
        }

    def shortest_path(self, start_id: str, end_id: str) -> Optional[List[str]]:
        """Find the unweighted shortest path (node IDs) between start and end node using BFS."""
        if start_id not in self.adj or end_id not in self.adj:
            return None
        if start_id == end_id:
            return [start_id]

        queue = deque([[start_id]])
        visited = {start_id}

        while queue:
            path = queue.popleft()
            node = path[-1]

            for neighbor in self.adj.get(node, []):
                if neighbor == end_id:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return None

    def get_connected_components(self) -> List[List[str]]:
        """Identify disjoint connected subgraphs."""
        visited: Set[str] = set()
        components: List[List[str]] = []

        for entity_id in self.adj:
            if entity_id not in visited:
                comp: List[str] = []
                q = deque([entity_id])
                visited.add(entity_id)

                while q:
                    curr = q.popleft()
                    comp.append(curr)
                    for nbr in self.adj.get(curr, []):
                        if nbr not in visited:
                            visited.add(nbr)
                            q.append(nbr)
                components.append(comp)
        return components
