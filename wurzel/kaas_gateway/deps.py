# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from supabase import Client, ClientOptions, create_client
from wurzel.kaas_gateway.settings import Settings, get_settings


def get_settings_dep() -> Settings:
    return get_settings()


def verify_internal_secret(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    x_secret: Annotated[str | None, Header(alias="X-Kaas-Gateway-Secret")] = None,
) -> None:
    if settings.KAAS_GATEWAY_INTERNAL_SECRET and x_secret != settings.KAAS_GATEWAY_INTERNAL_SECRET:
        raise HTTPException(status_code=401, detail="Invalid gateway secret")


def create_user_supabase(settings: Settings, authorization: str) -> Client:
    base = ClientOptions()
    opts = ClientOptions(
        headers={**base.headers, "Authorization": authorization},
        auto_refresh_token=False,
        persist_session=False,
    )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY, options=opts)


def create_service_supabase(settings: Settings) -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
