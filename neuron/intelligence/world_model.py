"""
VAMS ProPlay World Model
========================
Implements the Procedural World Model (ProPlay) with directed procedure graphs,
transition reliability embeddings, preplay planning (soft guidance),
and episodic refinement.

Reference: June 2026 ProPlay Paper
"""

import json
import math
import os
from typing import Dict, List, Tuple, Any, Optional

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


class SimpleTextEmbedding:
    """
    A lightweight, training-free bag-of-words embedding generator 
    to calculate text cosine similarity offline without API dependencies.
    """
    @staticmethod
    def get_vector(text: str) -> Dict[str, float]:
        words = re_find_words = [w.lower() for w in text.split() if len(w) > 1]
        freq: Dict[str, float] = {}
        for w in words:
            freq[w] = freq.get(w, 0.0) + 1.0
        
        # Normalize
        length = math.sqrt(sum(v**2 for v in freq.values()))
        if length == 0:
            return {}
        return {k: v / length for k, v in freq.items()}

    @staticmethod
    def cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
        dot_product = 0.0
        for k, val in v1.items():
            if k in v2:
                dot_product += val * v2[k]
        return dot_product


class ProPlayWorldModel:
    """
    Procedural World Model for VAMS agents.
    Maintains a directed procedure graph tracking transitional reliability scores
    and provides task-specific soft guidance before execution.
    """
    def __init__(self, filepath: str = ".data/memory/procedure_graph.json"):
        self.filepath = filepath
        self.procedures: Dict[str, str] = {}  # Name -> Description
        # Transitions representation: (u, v) -> {"rewards": List[float], "embeddings": List[Dict[str, float]]}
        self.transitions: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.load_graph()

    def load_graph(self):
        """Load the procedure graph from local JSON storage."""
        if not os.path.exists(self.filepath):
            # Ensure folder exists
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            self.save_graph()
            return
            
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                self.procedures = data.get("procedures", {})
                
                # Deserialization of transitions dict
                trans_data = data.get("transitions", [])
                for item in trans_data:
                    u, v = item["from"], item["to"]
                    self.transitions[(u, v)] = {
                        "rewards": item.get("rewards", []),
                        "embeddings": item.get("embeddings", [])
                    }
        except Exception as e:
            # Fallback on parse failure
            self.procedures = {}
            self.transitions = {}

    def save_graph(self):
        """Serialize the procedure graph to local JSON storage."""
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            
            # Serialize transitions dict
            serialized_transitions = []
            for (u, v), trans_info in self.transitions.items():
                serialized_transitions.append({
                    "from": u,
                    "to": v,
                    "rewards": trans_info["rewards"],
                    "embeddings": trans_info["embeddings"]
                })
                
            data = {
                "procedures": self.procedures,
                "transitions": serialized_transitions
            }
            with open(self.filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def add_procedure(self, name: str, description: str):
        """Add a procedural node."""
        self.procedures[name] = description
        self.save_graph()

    def record_transition(self, from_proc: str, to_proc: str, reward: float, task_description: str):
        """
        Record a transition between two procedures with its reward 
        and updates the edge reliability embeddings.
        """
        if from_proc not in self.procedures:
            self.add_procedure(from_proc, f"Procedure: {from_proc}")
        if to_proc not in self.procedures:
            self.add_procedure(to_proc, f"Procedure: {to_proc}")
            
        edge_key = (from_proc, to_proc)
        if edge_key not in self.transitions:
            self.transitions[edge_key] = {"rewards": [], "embeddings": []}
            
        # Get embedding vector (using SimpleTextEmbedding)
        emb_vector = SimpleTextEmbedding.get_vector(task_description)
        
        self.transitions[edge_key]["rewards"].append(reward)
        self.transitions[edge_key]["embeddings"].append(emb_vector)
        self.save_graph()

    def get_edge_reliability(self, from_proc: str, to_proc: str, task_intent_vector: Dict[str, float]) -> float:
        """
        Calculate transition suitability score using Cosine Similarity of 
        current task intent against historical transition embeddings weighted by reward.
        """
        edge_key = (from_proc, to_proc)
        if edge_key not in self.transitions or not self.transitions[edge_key]["embeddings"]:
            return 0.0
            
        trans_info = self.transitions[edge_key]
        similarities = []
        
        for reward, emb in zip(trans_info["rewards"], trans_info["embeddings"]):
            sim = SimpleTextEmbedding.cosine_similarity(task_intent_vector, emb)
            # Weighted transition suitability: Similarity * Reward
            similarities.append(sim * reward)
            
        # Return average suitability score
        return sum(similarities) / len(similarities)

    def get_soft_guidance(self, task_intent: str) -> str:
        """
        Project the optimal path across the Procedure Graph based on task suitability.
        Returns a formatted 'Soft Guidance' string.
        """
        if not self.procedures or not self.transitions:
            return "SOFT GUIDANCE PRIOR: No prior procedural history available."

        intent_vector = SimpleTextEmbedding.get_vector(task_intent)
        
        # Build weighted network structure
        weighted_edges: List[Tuple[str, str, float]] = []
        for (u, v) in self.transitions.keys():
            suitability = self.get_edge_reliability(u, v, intent_vector)
            # We want suitability to be high, so weight = max(0, suitability)
            weighted_edges.append((u, v, max(0.0, suitability)))

        # Find the path that maximizes reliability.
        # Simple DP/DAG search or NetworkX if available
        best_path: List[str] = []
        if HAS_NETWORKX:
            try:
                g = nx.DiGraph()
                for u, v, w in weighted_edges:
                    # NetworkX shortest_path uses distance, so invert weight: cost = 1 / (w + 1e-5)
                    g.add_edge(u, v, weight=1.0 / (w + 1e-5))
                
                # Check for reachable paths from nodes
                # Since start/end may not be defined, look for highest scoring path
                all_paths: List[Tuple[List[str], float]] = []
                for start in self.procedures.keys():
                    for end in self.procedures.keys():
                        if start == end:
                            continue
                        if nx.has_path(g, start, end):
                            path = nx.shortest_path(g, source=start, target=end, weight="weight")
                            # Compute actual total path suitability score
                            path_suitability = sum(
                                next(w for src, dest, w in weighted_edges if src == path[i] and dest == path[i+1])
                                for i in range(len(path) - 1)
                            )
                            all_paths.append((path, path_suitability))
                if all_paths:
                    all_paths.sort(key=lambda x: x[1], reverse=True)
                    best_path = all_paths[0][0]
            except Exception:
                pass

        # Pure-Python fallback DAG search if NetworkX is absent or fails to find paths
        if not best_path:
            # Direct greedy search starting from any root node
            # Find nodes with in-degree 0
            all_nodes = set(self.procedures.keys())
            dest_nodes = {v for (u, v) in self.transitions.keys()}
            roots = list(all_nodes - dest_nodes)
            if not roots:
                roots = list(all_nodes)[:1]
                
            best_score = -1.0
            for root in roots:
                current = root
                path = [current]
                score = 0.0
                visited = {current}
                
                while True:
                    # Get outgoing edges
                    outgoings = [
                        (v, w) for u, v, w in weighted_edges 
                        if u == current and v not in visited
                    ]
                    if not outgoings:
                        break
                    # Greedily choose highest score transition
                    outgoings.sort(key=lambda x: x[1], reverse=True)
                    next_node, weight = outgoings[0]
                    path.append(next_node)
                    score += weight
                    visited.add(next_node)
                    current = next_node
                    
                if score > best_score and len(path) > 1:
                    best_path = path
                    best_score = score

        if not best_path:
            return "SOFT GUIDANCE PRIOR: Directed procedure graph has no sequential pathways."
            
        return f"SOFT GUIDANCE PRIOR: Recommended procedural flow is: {' -> '.join(best_path)}"
