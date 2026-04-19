"""Production-side adapters for Agentic Operating Harness v1.

These modules bridge the deterministic AGH v1 agents to the live Metis
spine (Brain bundle, transcript ingest history, registry surface) *in
read-only mode*. They never mutate the registry or Brain bundle - the
proposal-only doctrine still applies.
"""
