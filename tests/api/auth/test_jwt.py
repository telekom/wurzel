# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for JWT audience and expiration verification."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest

jwt = pytest.importorskip("jwt", reason="wurzel[fastapi] not installed")

from wurzel.api.auth.jwt import _decode_token  # noqa: E402
from wurzel.api.auth.settings import AuthSettings  # noqa: E402

_SECRET = b"0123456789abcdef0123456789abcdef"  # pragma: allowlist secret


def _auth_settings() -> AuthSettings:
    return AuthSettings(
        JWKS_URL="http://fake.local/jwks.json",
        JWT_AUDIENCE="authenticated",
        ALGORITHM="HS256",
        ENABLED=True,
    )


def _jwks_for_secret(secret: bytes) -> dict[str, list[dict[str, str]]]:
    key = base64.urlsafe_b64encode(secret).rstrip(b"=").decode("ascii")
    return {"keys": [{"k": key}]}


def _token(payload: dict, secret: bytes) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def test_decode_token_hs256_accepts_expected_audience():
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": now + timedelta(minutes=5),
    }

    decoded = _decode_token(_token(payload, _SECRET), _auth_settings(), _jwks_for_secret(_SECRET))

    assert decoded["sub"] == "user-1"


def test_decode_token_hs256_rejects_missing_audience():
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "email": "user@example.com",
        "exp": now + timedelta(minutes=5),
    }

    with pytest.raises(jwt.exceptions.MissingRequiredClaimError):
        _decode_token(_token(payload, _SECRET), _auth_settings(), _jwks_for_secret(_SECRET))


def test_decode_token_hs256_rejects_wrong_audience():
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "email": "user@example.com",
        "aud": "wrong",
        "exp": now + timedelta(minutes=5),
    }

    with pytest.raises(jwt.exceptions.InvalidAudienceError):
        _decode_token(_token(payload, _SECRET), _auth_settings(), _jwks_for_secret(_SECRET))


def test_decode_token_hs256_rejects_expired_token():
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": now - timedelta(minutes=1),
    }

    with pytest.raises(jwt.exceptions.ExpiredSignatureError):
        _decode_token(_token(payload, _SECRET), _auth_settings(), _jwks_for_secret(_SECRET))
