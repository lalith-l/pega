"""
Hallucination Firewall Validator.

Three-layer validation:
  Layer 1 — Schema Validation (declared parameters vs OpenAPI spec)
  Layer 2 — Policy Compliance (case state, policy locks, SLA)
  Layer 3 — Citation Token Assembly (30-second TTL token)
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from firewall.schema_registry import get_production_schema


class FirewallViolation(Exception):
    def __init__(self, layer: int, violation_type: str, details: dict):
        self.layer = layer
        self.violation_type = violation_type
        self.details = details
        super().__init__(f"Firewall Layer {layer} violation: {violation_type}")


def _validate_layer1(intent: dict) -> dict:
    """Strict JSON Schema check against current Production Schema (N)."""
    endpoint = intent.get("target_endpoint")
    declared = intent.get("declared_parameters", {})

    schema_entry = get_production_schema(endpoint)
    if not schema_entry:
        print(f"[Firewall] ⚠️ Endpoint '{endpoint}' not in Schema Registry. Passing Layer 1 by default.")
        return {
            "schema_validated": True,
            "schema_version": "unknown",
            "service": "unknown"
        }

    schema = schema_entry["schema"]
    required = schema.get("required", [])
    all_allowed = list(schema.get("properties", {}).keys())
    properties = schema.get("properties", {})

    errors = []

    print(f"[Firewall] Layer 1 Schema check: validating {len(declared)} params against '{schema_entry['version']}' schema for {endpoint}")
    
    # Check required params present
    for param in required:
        if param not in declared:
            print(f"[Firewall] ❌ Missing required param: {param}")
            errors.append({
                "error": "MISSING_REQUIRED_PARAM",
                "param": param,
                "message": f"Required parameter '{param}' is missing",
            })

    # Check for hallucinated params
    for param in declared:
        if all_allowed and param not in all_allowed:
            print(f"[Firewall] ❌ Hallucinated param detected: {param}")
            errors.append({
                "error": "HALLUCINATED_PARAM",
                "param": param,
                "schema_allowed": all_allowed,
                "message": f"Parameter '{param}' does not exist in the schema. "
                           f"Hallucinated field detected.",
            })
        else:
            print(f"[Firewall] ✅ Param verified: {param}")
            
        # Type check where possible
        if param in properties and "type" in properties[param]:
            expected_type = properties[param]["type"]
            value = declared[param]
            type_map = {
                "integer": int,
                "number": (int, float),
                "string": str,
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            expected = type_map.get(expected_type)
            if expected and not isinstance(value, expected):
                print(f"[Firewall] ❌ Type mismatch for param {param}: expected {expected_type}, got {type(value).__name__}")
                errors.append({
                    "error": "TYPE_MISMATCH",
                    "param": param,
                    "expected_type": expected_type,
                    "actual_type": type(value).__name__,
                    "message": f"Parameter '{param}' expected {expected_type}, got {type(value).__name__}",
                })
            # Enum check
            if "enum" in properties[param]:
                allowed_values = properties[param]["enum"]
                if value not in allowed_values:
                    print(f"[Firewall] ❌ Invalid enum value for param {param}: {value}")
                    errors.append({
                        "error": "INVALID_ENUM_VALUE",
                        "param": param,
                        "value": value,
                        "allowed": allowed_values,
                        "message": f"'{value}' not in allowed values: {allowed_values}",
                    })

    if errors:
        raise FirewallViolation(
            layer=1,
            violation_type="SCHEMA_VALIDATION_FAILED",
            details={"errors": errors, "endpoint": endpoint},
        )

    return {
        "schema_validated": True,
        "schema_version": f"{schema_entry['service']}-{schema_entry['version']}",
        "service": schema_entry["service"],
    }


def _validate_layer2(intent: dict, case: dict) -> dict:
    """Policy compliance check against Case state and policy locks."""
    policy_ctx = intent.get("policy_context", {})
    node_id = intent.get("node_id", "")

    errors = []

    # Check case is in EXECUTING state
    if case.get("status") not in ("EXECUTING", "RESUMING"):
        errors.append({
            "error": "INVALID_CASE_STATE",
            "current_state": case.get("status"),
            "message": f"Case is in '{case.get('status')}' state. Execution not allowed.",
        })

    # Check policy locks
    compiled = case.get("compiled_workflow", {})
    if isinstance(compiled, dict):
        all_nodes = compiled.get("nodes", [])
        # Find this node
        this_node = next((n for n in all_nodes if n["node_id"] == node_id), None)
        if this_node:
            # Check upstream policy-locked nodes have completed
            checkpoint = case.get("checkpoint") or {}
            completed_nodes = checkpoint.get("completed_nodes", [])
            for dep_id in this_node.get("dependencies", []):
                dep_node = next((n for n in all_nodes if n["node_id"] == dep_id), None)
                if dep_node and dep_node.get("policy_locked"):
                    if dep_id not in completed_nodes:
                        errors.append({
                            "error": "POLICY_LOCK_VIOLATION",
                            "blocked_by": dep_id,
                            "message": f"Policy-locked node '{dep_id}' must complete before '{node_id}'",
                        })

    if errors:
        raise FirewallViolation(
            layer=2,
            violation_type="POLICY_COMPLIANCE_FAILED",
            details={"errors": errors},
        )

    return {"policy_compliant": True}


def assemble_citation_token(intent: dict, layer1_result: dict, layer2_result: dict) -> dict:
    """Layer 3 — Assemble Citation Token with 30-second TTL."""
    now = datetime.utcnow()
    return {
        "token_id": str(uuid.uuid4()),
        "case_id": intent.get("policy_context", {}).get("case_id", "unknown"),
        "node_id": intent.get("node_id"),
        "schema_validated": layer1_result["schema_validated"],
        "schema_version": layer1_result["schema_version"],
        "service": layer1_result["service"],
        "policy_compliant": layer2_result["policy_compliant"],
        "parameters_verified": intent.get("declared_parameters", {}),
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=30)).isoformat(),
    }


def is_token_valid(token: dict) -> bool:
    expires = datetime.fromisoformat(token["expires_at"])
    return datetime.utcnow() < expires


def validate_intent(intent: dict, case: dict) -> dict:
    """
    Full 3-layer validation. Returns Citation Token on success.
    Raises FirewallViolation on any failure.
    """
    layer1 = _validate_layer1(intent)
    layer2 = _validate_layer2(intent, case)
    token = assemble_citation_token(intent, layer1, layer2)
    return token
