"""Metis Brain v0 — artifact, promotion gate, active horizon registry (Unified Product Spec §6.1–6.3)."""

from metis_brain.bundle import (
    BrainBundleV0,
    brain_bundle_path,
    bundle_ready_for_horizon,
    load_brain_bundle_v0,
    try_load_brain_bundle_v0,
    validate_active_registry_integrity,
)

__all__ = [
    "BrainBundleV0",
    "brain_bundle_path",
    "bundle_ready_for_horizon",
    "load_brain_bundle_v0",
    "try_load_brain_bundle_v0",
    "validate_active_registry_integrity",
]
