"""
Builds an in-memory prerequisite graph from the Concept table using
NetworkX. Small per-subject graphs don't need a graph database — this
keeps the stack simple while still giving you real graph algorithms
(topological sort, ancestor lookup) to talk about in the viva.
"""
import networkx as nx
from sqlalchemy.orm import Session

from app.models import Concept


def build_graph(db: Session, student_id: int) -> nx.DiGraph:
    graph = nx.DiGraph()
    concepts = db.query(Concept).filter(Concept.student_id == student_id).all()

    for concept in concepts:
        graph.add_node(concept.name)

    for concept in concepts:
        prereqs = [p.strip() for p in (concept.prerequisites or "").split(",") if p.strip()]
        for prereq in prereqs:
            graph.add_edge(prereq, concept.name)  # prereq -> concept

    return graph


def get_prerequisite_map(db: Session, student_id: int) -> dict:
    """Returns {concept_name: [direct_prerequisites]} for planner_tools."""
    graph = build_graph(db, student_id)
    return {node: list(graph.predecessors(node)) for node in graph.nodes}


def get_learning_order(db: Session, student_id: int) -> list[str]:
    """
    Topological sort: a valid order to learn all concepts such that every
    prerequisite comes before the concept that depends on it. Falls back
    to node list if the graph has a cycle (shouldn't happen, but don't crash).
    """
    graph = build_graph(db, student_id)
    try:
        return list(nx.topological_sort(graph))
    except nx.NetworkXUnfeasible:
        return list(graph.nodes)
