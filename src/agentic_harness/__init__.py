"""Agentic Operating Harness v1.

Packet-governed, bounded-agent operating harness that sits on top of the
deterministic phase 48-52 rails. Agents inside this module are limited to
``enqueue`` / ``propose`` / ``classify`` operations - they never mutate the
active registry, the brain bundle, or PIT truth directly.

See ``docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md`` and the
work-order ``METIS_Agentic_Operating_Harness_v1.md`` for the full contract.
"""

from __future__ import annotations
