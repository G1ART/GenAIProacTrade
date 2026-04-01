"""Supabase service-role 클라이언트."""

from __future__ import annotations

from supabase import Client, create_client

from config import Settings


def get_supabase_client(settings: Settings) -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
