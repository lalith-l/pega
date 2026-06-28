"""
Neo4j graph operations for MORPHEUS.

Graph schema:
  (:WorkflowNode {node_id, case_id, node_type, label, status, ...})
  (:AgentNode {name})
  (:TRCSession {session_id, case_id, attempt_number})

  (wn1)-[:TRIGGERED]->(wn2)
  (wn1)-[:RUNS_PARALLEL_WITH]->(wn2)
  (agent)-[:FLAGGED {reason, severity, dispute_type}]->(wn)
  (agent)-[:APPROVED {reasoning}]->(wn)
  (adg)-[:DECIDED {path, confidence, reasoning}]->(wn)
  (trc)-[:AMENDED]->(wn)
"""
from typing import Any, Optional
from db import get_neo4j_driver


class Neo4jService:

    # ─── Schema Version Registry ─────────────────────────────────────────
    async def save_schema_version(self, service: str, version: str, spec: dict):
        """Save an API schema version to Neo4j."""
        import json
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run(
                """
                MERGE (sv:SchemaVersion {api_name: $service, version: $version})
                SET sv.fetched_at = timestamp(),
                    sv.spec_json = $spec_json
                """,
                service=service, version=version, spec_json=json.dumps(spec)
            )

    # ─── Case graph setup ────────────────────────────────────────────────
    async def create_case_graph(self, case_id: str, nodes: list[dict], objective: str):
        """Write initial workflow nodes and edges from compiled workflow."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            # Create Case node
            await session.run(
                """
                MERGE (c:MorpheusCase {case_id: $case_id})
                SET c.objective = $objective, c.created_at = timestamp()
                """,
                case_id=case_id, objective=objective
            )
            # Create WorkflowNode nodes
            for node in nodes:
                await session.run(
                    """
                    CREATE (wn:WorkflowNode {
                        node_id: $node_id,
                        case_id: $case_id,
                        node_type: $node_type,
                        label: $label,
                        description: $description,
                        status: 'PENDING',
                        created_at: timestamp()
                    })
                    """,
                    node_id=node["node_id"],
                    case_id=case_id,
                    node_type=node["node_type"],
                    label=node["label"],
                    description=node.get("description", ""),
                )
            # Create TRIGGERED edges from dependencies
            for node in nodes:
                for dep_id in node.get("dependencies", []):
                    await session.run(
                        """
                        MATCH (a:WorkflowNode {node_id: $dep_id, case_id: $case_id})
                        MATCH (b:WorkflowNode {node_id: $node_id, case_id: $case_id})
                        MERGE (a)-[:TRIGGERED]->(b)
                        """,
                        dep_id=dep_id, node_id=node["node_id"], case_id=case_id
                    )
            # Create RUNS_PARALLEL_WITH edges
            for node in nodes:
                for par_id in node.get("can_run_parallel_with", []):
                    await session.run(
                        """
                        MATCH (a:WorkflowNode {node_id: $node_id, case_id: $case_id})
                        MATCH (b:WorkflowNode {node_id: $par_id, case_id: $case_id})
                        MERGE (a)-[:RUNS_PARALLEL_WITH]->(b)
                        """,
                        node_id=node["node_id"], par_id=par_id, case_id=case_id
                    )

    async def rollback_to_node(self, case_id: str, target_node_id: str):
        """Rollback executions occurring after the target_node_id."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            # Find the execution of the target node, and delete all execution nodes that come after it via [:NEXT*]
            await session.run(
                """
                MATCH (c:MorpheusCase {case_id: $case_id})-[:HAS_EXECUTION]->(target:Execution {node_id: $target_node_id})
                WITH target ORDER BY target.started_at DESC LIMIT 1
                MATCH (target)-[:NEXT*]->(downstream:Execution)
                DETACH DELETE downstream
                """,
                case_id=case_id, target_node_id=target_node_id
            )

    # ─── Agent verdicts ──────────────────────────────────────────────────
    async def write_agent_verdicts(self, case_id: str, agent_name: str, verdicts: list[dict]):
        """Write FLAGGED or APPROVED edges for an agent's court verdicts."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            # Ensure Agent node exists
            await session.run(
                "MERGE (:AgentNode {name: $name})", name=agent_name
            )
            for v in verdicts:
                rel_type = "FLAGGED" if v["verdict"] == "DISPUTE" else "APPROVED"
                if rel_type == "FLAGGED":
                    await session.run(
                        f"""
                        MATCH (agent:AgentNode {{name: $agent}})
                        MATCH (wn:WorkflowNode {{node_id: $node_id, case_id: $case_id}})
                        CREATE (agent)-[:FLAGGED {{
                            reason: $reasoning,
                            severity: $severity,
                            dispute_type: $dispute_type,
                            timestamp: timestamp()
                        }}]->(wn)
                        """,
                        agent=agent_name,
                        node_id=v["node_id"],
                        case_id=case_id,
                        reasoning=v.get("reasoning", ""),
                        severity=v.get("severity", "WARN"),
                        dispute_type=v.get("dispute_type", "UNKNOWN"),
                    )
                else:
                    await session.run(
                        """
                        MATCH (agent:AgentNode {name: $agent})
                        MATCH (wn:WorkflowNode {node_id: $node_id, case_id: $case_id})
                        CREATE (agent)-[:APPROVED {reasoning: $reasoning, timestamp: timestamp()}]->(wn)
                        """,
                        agent=agent_name,
                        node_id=v["node_id"],
                        case_id=case_id,
                        reasoning=v.get("reasoning", ""),
                    )

    # ─── Node execution events ───────────────────────────────────────────
    async def update_node_status(self, case_id: str, node_id: str, status: str,
                                  output: Optional[dict] = None):
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run(
                """
                MATCH (wn:WorkflowNode {node_id: $node_id, case_id: $case_id})
                SET wn.status = $status,
                    wn.updated_at = timestamp(),
                    wn.output = $output
                """,
                node_id=node_id, case_id=case_id, status=status,
                output=str(output) if output else ""
            )

    async def record_execution(self, case_id: str, node_id: str, status: str, output: Optional[dict] = None, input_json: Optional[dict] = None):
        """Record an individual execution node."""
        import json
        import uuid
        exec_id = str(uuid.uuid4())
        driver = get_neo4j_driver()
        async with driver.session() as session:
            # 1. Update the static workflow node status
            await self.update_node_status(case_id, node_id, status, output)
            
            # 2. Create the execution node linked to the case and the previous execution
            await session.run(
                """
                MATCH (c:MorpheusCase {case_id: $case_id})
                // Find the latest execution node if it exists
                OPTIONAL MATCH (c)-[:HAS_EXECUTION]->(last_exec:Execution)
                WITH c, last_exec ORDER BY last_exec.started_at DESC LIMIT 1
                
                CREATE (e:Execution {
                    id: $exec_id,
                    case_id: $case_id,
                    node_id: $node_id,
                    status: $status,
                    started_at: timestamp(),
                    input_json: $input,
                    output_json: $output
                })
                CREATE (c)-[:HAS_EXECUTION]->(e)
                
                // Link to previous execution if exists
                WITH last_exec, e
                WHERE last_exec IS NOT NULL
                CREATE (last_exec)-[:NEXT]->(e)
                """,
                case_id=case_id, exec_id=exec_id, node_id=node_id, status=status,
                input=json.dumps(input_json) if input_json else "",
                output=json.dumps(output) if output else ""
            )
            return exec_id
            
    async def record_firewall_result(self, case_id: str, node_id: str, passed: bool, details: dict):
        """Record firewall result and link it to the latest execution node."""
        import json
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run(
                """
                MATCH (c:MorpheusCase {case_id: $case_id})-[:HAS_EXECUTION]->(e:Execution {node_id: $node_id})
                WITH e ORDER BY e.started_at DESC LIMIT 1
                
                CREATE (f:FirewallResult {
                    passed: $passed,
                    details: $details,
                    timestamp: timestamp()
                })
                CREATE (e)-[:TRIGGERED_FIREWALL]->(f)
                """,
                case_id=case_id, node_id=node_id, passed=passed,
                details=json.dumps(details)
            )

    async def get_full_audit_trail(self, case_id: str) -> list[dict]:
        """Query 2 - Full Case Audit Trail from Neo4j."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (c:MorpheusCase {case_id: $case_id})-[:HAS_EXECUTION]->(e:Execution)
                OPTIONAL MATCH (e)-[:TRIGGERED_FIREWALL]->(f:FirewallResult)
                RETURN e.node_id AS node_id, e.status AS status, e.started_at AS started_at,
                       e.input_json AS input_json, e.output_json AS output_json,
                       f.passed AS fw_passed, f.details AS fw_details
                ORDER BY e.started_at ASC
                """,
                case_id=case_id
            )
            records = await result.fetch(1000)
            return [dict(r) for r in records]

    async def get_amendment_history(self, case_id: str) -> list[dict]:
        """Query 3 - Amendment History from Neo4j."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (c:MorpheusCase {case_id: $case_id})-[:HAS_AMENDMENT]->(a:Amendment)
                RETURN a.amendment_number AS amendment_number, a.patch_type AS patch_type,
                       a.rationale AS rationale, a.created_at AS created_at
                ORDER BY a.amendment_number ASC
                """,
                case_id=case_id
            )
            records = await result.fetch(100)
            return [dict(r) for r in records]

    # ─── TRC causal chain query ──────────────────────────────────────────
    async def create_causal_graph(self, case_id: str, failed_node_id: str):
        """Build CausalNodes from the execution trace for shortestPath query."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            # First, clear any old CausalNodes for this case
            await session.run("MATCH (cn:CausalNode {case_id: $case_id}) DETACH DELETE cn", case_id=case_id)
            
            # Create Court Session as root
            await session.run(
                """
                CREATE (cn_court:CausalNode {
                    node_id: 'court_session',
                    case_id: $case_id,
                    is_root: true,
                    is_failure: false
                })
                """,
                case_id=case_id
            )
            
            # Map Execution nodes directly to CausalNodes
            await session.run(
                """
                MATCH (c:MorpheusCase {case_id: $case_id})-[:HAS_EXECUTION]->(e:Execution)
                CREATE (cn:CausalNode {
                    node_id: e.node_id,
                    case_id: $case_id,
                    is_root: false,
                    is_failure: (e.node_id = $failed_node_id)
                })
                """,
                case_id=case_id, failed_node_id=failed_node_id
            )

            # Reconstruct causality based on static dependencies
            await session.run(
                """
                MATCH (cn1:CausalNode {case_id: $case_id})
                MATCH (cn2:CausalNode {case_id: $case_id})
                MATCH (wn1:WorkflowNode {node_id: cn1.node_id, case_id: $case_id})-[:TRIGGERED]->(wn2:WorkflowNode {node_id: cn2.node_id, case_id: $case_id})
                MERGE (cn1)-[:CAUSED]->(cn2)
                """,
                case_id=case_id
            )
            
            # Link Court Session to execution nodes with no incoming causality
            await session.run(
                """
                MATCH (cn_court:CausalNode {case_id: $case_id, node_id: 'court_session'})
                MATCH (cn_exec:CausalNode {case_id: $case_id})
                WHERE cn_exec.node_id <> 'court_session'
                AND NOT ()-[:CAUSED]->(cn_exec)
                MERGE (cn_court)-[:CAUSED]->(cn_exec)
                """,
                case_id=case_id
            )

    async def get_causal_chain(self, case_id: str, failed_node_id: str) -> dict:
        """
        Query 1 - TRC Causal Chain using shortestPath over CausalNodes.
        Returns: {path_nodes, flagged_warnings, raw_path}
        """
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH path = (root:CausalNode {case_id: $case_id, is_root: true})
                  -[:CAUSED*0..15]->
                  (failure:CausalNode {case_id: $case_id, is_failure: true})
                WITH path, nodes(path) AS path_nodes
                ORDER BY length(path) ASC LIMIT 1
                UNWIND path_nodes AS n
                // Join back to WorkflowNode to get label and agent flags
                OPTIONAL MATCH (wn:WorkflowNode {node_id: n.node_id, case_id: $case_id})
                OPTIONAL MATCH (agent:AgentNode)-[f:FLAGGED]->(wn)
                RETURN
                    [nd IN nodes(path) | {
                        node_id: nd.node_id
                    }] AS raw_path,
                    COLLECT(DISTINCT {
                        node_id: n.node_id,
                        label: CASE WHEN n.node_id = 'court_session' THEN 'Architecture Court (v2.1 Schema Injected)' ELSE wn.label END,
                        status: CASE WHEN n.node_id = 'court_session' THEN 'COMPLETED' ELSE wn.status END,
                        node_type: CASE WHEN n.node_id = 'court_session' THEN 'COURT' ELSE wn.node_type END
                    }) AS path_nodes,
                    COLLECT(DISTINCT {
                        agent: agent.name,
                        node_id: wn.node_id,
                        reason: f.reason,
                        severity: f.severity,
                        dispute_type: f.dispute_type
                    }) AS flagged_warnings
                LIMIT 1
                """,
                case_id=case_id
            )
            record = await result.single()
            if not record or not record.get("path_nodes"):
                # Fallback: just return the failed node if path doesn't exist
                return {
                    "path_nodes": [{"node_id": failed_node_id, "label": "Unknown", "status": "FAILED"}],
                    "flagged_warnings": [],
                }
                
            path_nodes = record["path_nodes"]
            # Deduplicate flagged warnings and remove nulls
            warnings = []
            for w in (record["flagged_warnings"] or []):
                if w.get("agent") and w not in warnings:
                    warnings.append(w)
                    
            return {
                "path_nodes": path_nodes,
                "flagged_warnings": warnings,
            }

    # ─── Nearby warnings (for TRC autopsy) ──────────────────────────────
    async def get_nearby_flags(self, case_id: str, node_id: str, hops: int = 2) -> list[dict]:
        """Find all FLAGGED edges within N hops of a node."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run(
                f"""
                MATCH (center:WorkflowNode {{node_id: $node_id, case_id: $case_id}})-[:TRIGGERED|RUNS_PARALLEL_WITH*0..{hops}]-(nearby:WorkflowNode)
                MATCH (agent:AgentNode)-[f:FLAGGED]->(nearby)
                RETURN agent.name AS agent, nearby.node_id AS node_id,
                       nearby.label AS label, f.reason AS reason,
                       f.severity AS severity, f.dispute_type AS dispute_type
                """,
                node_id=node_id, case_id=case_id
            )
            records = await result.fetch(50)
            return [dict(r) for r in records]

    # ─── Write amendment ─────────────────────────────────────────────────
    async def create_amendment(self, case_id: str, patch_id: str, patch_type: str, rationale: str, amendment_number: int):
        """Record TRC patch as graph amendment linked to Case."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run(
                """
                MATCH (c:MorpheusCase {case_id: $case_id})
                SET c.amendment_count = COALESCE(c.amendment_count, 0) + 1
                CREATE (a:Amendment {
                    patch_id: $patch_id,
                    patch_type: $patch_type,
                    rationale: $rationale,
                    amendment_number: $amendment_number,
                    created_at: timestamp()
                })
                CREATE (c)-[:HAS_AMENDMENT]->(a)
                """,
                case_id=case_id, patch_id=patch_id,
                patch_type=patch_type, rationale=rationale,
                amendment_number=amendment_number
            )

    async def write_amendment(self, case_id: str, trc_session_id: str,
                               attempt_number: int, patch_type: str,
                               affected_node_ids: list[str], new_nodes: list[dict]):
        """Record TRC patch as graph amendment."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run(
                """
                CREATE (trc:TRCSession {
                    session_id: $session_id,
                    case_id: $case_id,
                    attempt_number: $attempt,
                    patch_type: $patch_type,
                    created_at: timestamp()
                })
                """,
                session_id=trc_session_id, case_id=case_id,
                attempt=attempt_number, patch_type=patch_type
            )
            for node_id in affected_node_ids:
                await session.run(
                    """
                    MATCH (trc:TRCSession {session_id: $session_id})
                    MATCH (wn:WorkflowNode {node_id: $node_id, case_id: $case_id})
                    CREATE (trc)-[:AMENDED]->(wn)
                    """,
                    session_id=trc_session_id, node_id=node_id, case_id=case_id
                )
            # Create new nodes from patch
            for node in new_nodes:
                await session.run(
                    """
                    CREATE (wn:WorkflowNode {
                        node_id: $node_id,
                        case_id: $case_id,
                        node_type: $node_type,
                        label: $label,
                        description: $description,
                        status: 'PENDING',
                        is_patch: true,
                        created_at: timestamp()
                    })
                    WITH wn
                    MATCH (trc:TRCSession {session_id: $session_id})
                    CREATE (trc)-[:CREATED]->(wn)
                    """,
                    node_id=node["node_id"],
                    case_id=case_id,
                    node_type=node.get("node_type", "DATA_TRANSFORM"),
                    label=node.get("label", "Patched Node"),
                    description=node.get("description", ""),
                    session_id=trc_session_id
                )

    # ─── ADG decision ────────────────────────────────────────────────────
    async def write_adg_decision(self, case_id: str, adg_node_id: str,
                                  chosen_node_id: str, confidence: float,
                                  reasoning: str, is_human_override: bool):
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run(
                """
                MATCH (adg:WorkflowNode {node_id: $adg_id, case_id: $case_id})
                MATCH (chosen:WorkflowNode {node_id: $chosen_id, case_id: $case_id})
                CREATE (adg)-[:DECIDED {
                    confidence: $confidence,
                    reasoning: $reasoning,
                    is_human_override: $is_override,
                    timestamp: timestamp()
                }]->(chosen)
                """,
                adg_id=adg_node_id, case_id=case_id,
                chosen_id=chosen_node_id, confidence=confidence,
                reasoning=reasoning, is_override=is_human_override
            )


neo4j_service = Neo4jService()
