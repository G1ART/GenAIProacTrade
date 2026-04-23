"""Product Shell view-model layer (Patch 10A).

This package is the only translation surface between METIS internal
state (brain bundles, spectrum rows, provenance enums, registry ids)
and the customer-facing Product Shell DTOs exposed under
``/api/product/*``. Anything leaving this package must be free of
engineering identifiers (see ``view_models._strip_engineering_ids``).
"""

from .view_models import (
    build_today_product_dto,
    strip_engineering_ids,
)

__all__ = [
    "build_today_product_dto",
    "strip_engineering_ids",
]
