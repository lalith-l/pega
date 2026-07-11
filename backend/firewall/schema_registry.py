"""
Schema Registry — Organic Hallucination Engine
Stores multiple versions of API schemas in Neo4j.
Provides N-1 to agents and N to Firewall.
"""
import json
from pathlib import Path
from typing import Optional
from neo4j_service import neo4j_service

SPECS_DIR = Path(__file__).parent / "specs"

# In-memory fallback/cache
_agent_registry: dict[str, dict] = {}
_production_registry: dict[str, dict] = {}

async def load_registry():
    """Load all specs from the specs/ directory at startup and sync to Neo4j."""
    global _agent_registry, _production_registry
    
    for spec_file in SPECS_DIR.glob("*.json"):
        with open(spec_file) as f:
            spec = json.load(f)
            
        service = spec["service"]
        version = spec["version"]
        
        # Save to Neo4j
        await neo4j_service.save_schema_version(service, version, spec)
        
        # Determine if it's N-1 (agent) or N (production)
        # For our demo, v2.1 is agent, v2.4 is production
        # In a real system, you'd sort by version.
        is_agent = "v2.1" in version
        is_production = "v2.4" in version
        
        for endpoint, schema in spec.get("endpoints", {}).items():
            entry = {
                "service": service,
                "version": version,
                "schema": schema,
            }
            if is_agent:
                _agent_registry[endpoint] = entry
            if is_production:
                _production_registry[endpoint] = entry
                
    print(f"[SchemaRegistry] Loaded {_agent_registry.keys()} (Agent) and {_production_registry.keys()} (Production)")

def get_agent_schema(endpoint: str) -> Optional[dict]:
    """Return N-1 schema for LLM agents."""
    return _match_schema(endpoint, _agent_registry)

def get_production_schema(endpoint: str) -> Optional[dict]:
    """Return N schema for Firewall validation."""
    return _match_schema(endpoint, _production_registry)

def _match_schema(endpoint: str, registry: dict) -> Optional[dict]:
    if endpoint in registry:
        return registry[endpoint]
    for registered_endpoint, schema in registry.items():
        if endpoint.startswith(registered_endpoint.rstrip("/")):
            return schema
    return None
