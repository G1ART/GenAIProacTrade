"""Patch 12 — invite-only Supabase auth + per-user telemetry guards.

This package provides the server-side surface needed for the Private Beta
rollout:

* stdlib HS256 JWT verifier (no ``PyJWT`` dependency).
* invite allowlist probe (reads ``beta_users_v1`` via the service role).
* request guard used by ``dispatch_json`` to gate ``/api/*`` routes.
* minimal Supabase REST client used for service-role reads/writes.

Every module sticks to the Python standard library with a single exception
— ``supabase_rest`` uses ``urllib.request`` — so the auth surface has zero
new runtime dependencies beyond what the repo already ships.
"""

from phase47_runtime.auth.jwt_verifier import (  # noqa: F401
    JwtVerifyResult,
    verify_supabase_jwt,
)
from phase47_runtime.auth.beta_allowlist import (  # noqa: F401
    BetaAllowlistResult,
    verify_user_is_active_beta,
)
from phase47_runtime.auth.guard import (  # noqa: F401
    AuthDecision,
    PUBLIC_API_PATHS,
    require_auth,
    user_id_alias,
)
from phase47_runtime.auth.supabase_rest import (  # noqa: F401
    SupabaseRestClient,
    SupabaseRestError,
)
