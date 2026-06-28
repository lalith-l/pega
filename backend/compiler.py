from datetime import datetime, timedelta
from typing import Dict, List, Any

class CompilationError(Exception):
    pass

def topological_sort(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Kahn's algorithm for topological sorting."""
    # Build adjacency list and in-degree counts
    in_degree = {n["node_id"]: 0 for n in nodes}
    adj = {n["node_id"]: [] for n in nodes}
    node_map = {n["node_id"]: n for n in nodes}
    
    for n in nodes:
        for dep in n.get("dependencies", []):
            if dep not in in_degree:
                continue # Ignore missing deps for simplicity
            adj[dep].append(n["node_id"])
            in_degree[n["node_id"]] += 1
            
    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    sorted_order = []
    
    while queue:
        current = queue.pop(0)
        sorted_order.append(node_map[current])
        for neighbor in adj[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                
    if len(sorted_order) != len(nodes):
        raise CompilationError("Cycle detected in graph dependencies")
        
    return sorted_order

def compile_workflow(case_id: str, objective: str, raw_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    AST Compilation:
    1. Topo sort
    2. Inject FIREWALL_GATE before every API_CALL
    3. Transform DECISION_GATE into ADG_GATE
    4. Bind SLA deadline
    5. Parallel Cluster Identification
    6. Policy Lock Enforcement
    """
    sorted_nodes = topological_sort(raw_nodes)
    
    compiled_nodes = []
    
    for node in sorted_nodes:
        # Policy Lock Enforcement from Compliance Agent
        verdicts = node.get("agent_verdicts", {})
        comp_verdict = verdicts.get("COMPLIANCE")
        if comp_verdict and comp_verdict.get("verdict") == "DISPUTE":
            if "POLICY" in comp_verdict.get("dispute_type", "") or comp_verdict.get("severity") == "BLOCK":
                node["policy_locked"] = True

        # If decision gate, upgrade to Adaptive Decisioning Gate (ADG)
        if node.get("node_type") == "DECISION_GATE":
            node["node_type"] = "ADG_GATE"
            
        # If API_CALL, inject a Firewall Gate before it
        if node.get("node_type") == "API_CALL":
            firewall_node = {
                "node_id": f"fw_{node['node_id']}",
                "node_type": "FIREWALL_GATE",
                "label": f"Firewall: {node.get('label', 'API')}",
                "description": "Auto-inserted Hallucination Firewall validation",
                "dependencies": node.get("dependencies", []),
                "guards": node["node_id"],
                "target_endpoint": node.get("target_endpoint")
            }
            # The actual action node now depends ONLY on the firewall
            node["dependencies"] = [firewall_node["node_id"]]
            compiled_nodes.append(firewall_node)
            
        compiled_nodes.append(node)
        
    # Parallel Cluster Identification
    parallel_clusters = []
    # Identify nodes that can run parallel with each other
    visited = set()
    for node in compiled_nodes:
        nid = node["node_id"]
        if nid in visited:
            continue
        parallel_with = node.get("can_run_parallel_with", [])
        if parallel_with:
            # Simple connected component for clusters
            cluster = {nid}
            cluster.update(parallel_with)
            visited.update(cluster)
            parallel_clusters.append(list(cluster))

    return {
        "case_id": case_id,
        "business_objective": objective,
        "compiled_at": datetime.utcnow().isoformat(),
        "sla_deadline": (datetime.utcnow() + timedelta(hours=24)).isoformat(), # Default 24h SLA
        "nodes": compiled_nodes,
        "total_nodes": len(compiled_nodes),
        "execution_order": [n["node_id"] for n in compiled_nodes],
        "parallel_clusters": parallel_clusters
    }
