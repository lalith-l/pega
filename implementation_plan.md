# Eliminating Hardcodes: The Organic Hallucination Engine

This plan covers the massive architectural upgrade from the simulated demo engine to the true, fully dynamic MORPHEUS system as defined in the "Master Insight" document. 

## User Review Required

> [!WARNING]
> **Missing Sections:** The document you provided cut off at the end. The sections `REPLACING SIMULATED NODE OUTPUTS — REAL API SANDBOXES`, `COMPLETE FREE STACK`, and `BUILD SEQUENCE — WEEK BY WEEK` were mostly empty.
> I will proceed with standard public API sandboxes (e.g., Stripe Test API, Twilio Test Credentials, SendGrid Sandbox) unless you have specific sandbox services you want me to use. Please confirm!

> [!IMPORTANT]
> **Neo4j Aura Integration:** The new design requires heavy use of Neo4j for the Living Case Object, Causal Chain traversal, and Schema Registry. I will implement these queries using the `neo4j` Python driver against your AuraDB credentials in `database.py`.

## Open Questions

1. **API Keys for Sandboxes**: To remove the `DEMO_NODE_OUTPUTS` simulation and make real API calls, we will need test API keys for Stripe, Twilio/SendGrid, etc. Shall I set up dummy local mock servers using FastAPI to act as these "sandboxes" for the sake of 100% local testing, or do you have real test API keys you want to inject into `config.py`? (Local mock servers that implement version N and N-1 of a schema are usually best for predictable drift demos without needing internet API keys).
2. **Render Workflows**: You mentioned "Track 1 — Render Workflows". Since requirement `b` from your initial prompt was *"Build and test 100% locally first"*, I will continue using FastAPI `BackgroundTasks` to simulate the Render background worker architecture locally. Is this acceptable for now?

## Proposed Changes

---

### Phase 1: The Schema Registry & Organic Version Drift

Implementation of the engine that causes the LLM to naturally hallucinate via version drift.

#### [MODIFY] [backend/firewall/specs/erp_mock_spec.json](file:///Users/lalithkumargn/Desktop/pega/backend/firewall/specs/erp_mock_spec.json)
- Refactor to include two distinct schema definitions: `v2.1` (N-1) and `v2.4` (N).
- Deliberately rename 3 parameters in `v2.4` (e.g., `vendor_ifsc_code` vs `vendor_acc_IFSC_2023`).

#### [MODIFY] [backend/firewall/schema_registry.py](file:///Users/lalithkumargn/Desktop/pega/backend/firewall/schema_registry.py)
- Connect to Neo4j to store and retrieve `(:SchemaVersion)` nodes.
- Implement `get_agent_schema(api_target)` which returns version N-1.
- Implement `get_production_schema(api_target)` which returns version N for the Firewall.

---

### Phase 2: Architecture Court (3-Round Debate)

#### [MODIFY] [backend/worker.py](file:///Users/lalithkumargn/Desktop/pega/backend/worker.py)
- Implement **Round 1**: Parallel execution of Architect, Security, Efficiency, and Compliance agents generating independent assessments.
- Implement **Round 2**: Sequential cross-examination where challengers object to Architect's R1 proposal, followed by Architect's revised R2 proposal.
- Implement **Round 3**: Algorithmic (non-LLM) conflict resolution based on agent votes.

#### [MODIFY] [backend/agents/base.py](file:///Users/lalithkumargn/Desktop/pega/backend/agents/base.py) & Agent Classes
- Inject the N-1 schema definitions into the agent context prompts when they propose `API_CALL` nodes so they organically generate the "wrong" payload.

---

### Phase 3: AST Graph Compilation

#### [NEW] [backend/compiler.py](file:///Users/lalithkumargn/Desktop/pega/backend/compiler.py)
- Implement Kahn's algorithm for topological sorting of workflow dependencies.
- Inject `firewall_gate` states automatically before every `action` node.
- Inject `adaptive_gate` states where Architect indicated a decision point.
- Enforce `policy_locked` flags.

#### [MODIFY] [backend/routers/court.py](file:///Users/lalithkumargn/Desktop/pega/backend/routers/court.py)
- Update `/court/compile` to use the new `compiler.py` logic.

---

### Phase 4: Execution Engine & Adaptive Decisioning Gate

#### [MODIFY] [backend/execution_engine.py](file:///Users/lalithkumargn/Desktop/pega/backend/execution_engine.py)
- Remove `DEMO_NODE_OUTPUTS` and `DEMO_BAD_PARAMS`.
- Implement an HTTP client to actually execute `action` nodes against sandbox URLs.
- Implement the Adaptive Decisioning Gate (ADG) logic: fetch Case history from Neo4j, prompt the LLM to choose a branch, and route execution.

---

### Phase 5: Neo4j Living Case Object & TRC Upgrade

#### [MODIFY] [backend/neo4j_service.py](file:///Users/lalithkumargn/Desktop/pega/backend/neo4j_service.py)
- Implement full graph schema (`:Case`, `:WorkflowNode`, `:AgentVote`, `:Execution`, `:FirewallResult`, `:Amendment`).
- Implement the TRC Shortest Path query: `MATCH path = shortestPath((root)-[*..]-(failure))` to extract the causal chain.

#### [MODIFY] [backend/trc/pipeline.py](file:///Users/lalithkumargn/Desktop/pega/backend/trc/pipeline.py)
- Update Phase 2 (Causal Chain Reconstruction) to use the Neo4j shortest path query instead of a simple linear array.

## Verification Plan

### Automated Tests
- N/A for this phase, will rely on end-to-end execution testing.

### Manual Verification
1. Convene a new Architecture Court. Verify 3-round debate outputs in the dashboard.
2. Compile the graph. Verify that `firewall_gate` nodes are automatically inserted before action nodes in the JSON state machine.
3. Execute the Case. Verify that the agent organically hallucinates the payload using the N-1 schema, and the Firewall catches it using the N schema, correctly triggering the TRC without any hardcoded trigger variables.
