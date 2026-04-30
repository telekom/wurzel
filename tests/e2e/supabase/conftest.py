# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import subprocess
import uuid
from base64 import urlsafe_b64decode
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")
pytest.importorskip("supabase", reason="wurzel[supabase] not installed")

from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.app import create_app  # noqa: E402
from wurzel.api.dependencies import _get_settings  # noqa: E402
from wurzel.api.middleware.otel import OTELSettings  # noqa: E402
from wurzel.api.routes.files.router import get_file_upload_service  # noqa: E402
from wurzel.api.services.file_service import FileUploadService  # noqa: E402
from wurzel.api.settings import APISettings  # noqa: E402
from wurzel.storage.file_storage_s3 import S3FileStorageService  # noqa: E402

pytestmark = pytest.mark.supabase_e2e

TEST_API_KEY = "supabase-e2e-api-key"  # pragma: allowlist secret


@dataclass(frozen=True)
class SupabaseLocalConfig:
    api_url: str
    anon_key: str
    service_role_key: str
    jwks_url: str


@dataclass(frozen=True)
class E2EAuthUsers:
    admin_user_id: str
    admin_token: str
    member_user_id: str
    member_token: str
    secret_editor_user_id: str
    secret_editor_token: str
    viewer_user_id: str
    viewer_token: str
    no_role_user_id: str
    no_role_token: str
    token_algorithm: str


@dataclass(frozen=True)
class LocalStackConfig:
    endpoint_url: str
    bucket_name: str
    region_name: str


def _token_algorithm(token: str) -> str:
    header, _, _ = token.partition(".")
    padded = header + "=" * (-len(header) % 4)
    parsed = json.loads(urlsafe_b64decode(padded).decode("utf-8"))
    return str(parsed["alg"])


def _create_user_and_token(cfg: SupabaseLocalConfig, *, email: str, password: str) -> tuple[str, str]:
    admin_headers = {
        "apikey": cfg.service_role_key,
        "Authorization": f"Bearer {cfg.service_role_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=15.0) as client:
        created = client.post(
            f"{cfg.api_url}/auth/v1/admin/users",
            headers=admin_headers,
            json={"email": email, "password": password, "email_confirm": True},
        )
        created.raise_for_status()
        user_id = created.json()["id"]

        login = client.post(
            f"{cfg.api_url}/auth/v1/token?grant_type=password",
            headers={"apikey": cfg.anon_key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
    return user_id, token


def _load_cli_env() -> dict[str, str]:
    result = subprocess.run(
        ["supabase", "status", "-o", "env"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("Supabase CLI is not running. Start it with: supabase start")
    env_map: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_map[key.strip()] = value.strip()
    return env_map


@lru_cache(maxsize=1)
def _resolve_supabase_local_config() -> SupabaseLocalConfig:
    cli_env = _load_cli_env()
    api_url = (cli_env.get("API_URL") or "").strip("'\"")
    anon_key = (cli_env.get("ANON_KEY") or "").strip("'\"")
    service_role_key = (cli_env.get("SERVICE_ROLE_KEY") or "").strip("'\"")
    if not api_url or not anon_key or not service_role_key:
        pytest.skip("supabase status -o env did not return API_URL, ANON_KEY and SERVICE_ROLE_KEY")
    if not api_url.startswith("http://") and not api_url.startswith("https://"):
        api_url = f"http://{api_url}"
    return SupabaseLocalConfig(
        api_url=api_url,
        anon_key=anon_key,
        service_role_key=service_role_key,
        jwks_url=f"{api_url}/auth/v1/.well-known/jwks.json",
    )


@pytest.fixture(scope="session")
def supabase_local_config() -> SupabaseLocalConfig:
    return _resolve_supabase_local_config()


@pytest.fixture(scope="session")
def auth_users(supabase_local_config: SupabaseLocalConfig) -> E2EAuthUsers:
    suffix = uuid.uuid4().hex[:10]
    password = f"E2ePass-{suffix}-Aa1!"

    admin_id, admin_token = _create_user_and_token(
        supabase_local_config,
        email=f"wurzel-e2e-admin-{suffix}@example.local",
        password=password,
    )
    member_id, member_token = _create_user_and_token(
        supabase_local_config,
        email=f"wurzel-e2e-member-{suffix}@example.local",
        password=password,
    )
    secret_editor_id, secret_editor_token = _create_user_and_token(
        supabase_local_config,
        email=f"wurzel-e2e-secret-editor-{suffix}@example.local",
        password=password,
    )
    viewer_id, viewer_token = _create_user_and_token(
        supabase_local_config,
        email=f"wurzel-e2e-viewer-{suffix}@example.local",
        password=password,
    )
    no_role_id, no_role_token = _create_user_and_token(
        supabase_local_config,
        email=f"wurzel-e2e-no-role-{suffix}@example.local",
        password=password,
    )

    return E2EAuthUsers(
        admin_user_id=admin_id,
        admin_token=admin_token,
        member_user_id=member_id,
        member_token=member_token,
        secret_editor_user_id=secret_editor_id,
        secret_editor_token=secret_editor_token,
        viewer_user_id=viewer_id,
        viewer_token=viewer_token,
        no_role_user_id=no_role_id,
        no_role_token=no_role_token,
        token_algorithm=_token_algorithm(admin_token),
    )


@pytest.fixture(scope="session")
def app(supabase_local_config: SupabaseLocalConfig, auth_users: E2EAuthUsers):
    from fastapi import Depends  # noqa: PLC0415
    from fastapi.security import HTTPBearer  # noqa: PLC0415

    from wurzel.api.auth.jwt import UserClaims, _verify_jwt  # noqa: PLC0415

    os.environ["SUPABASE__URL"] = supabase_local_config.api_url
    os.environ["SUPABASE__SERVICE_KEY"] = supabase_local_config.service_role_key
    os.environ["AUTH__JWKS_URL"] = supabase_local_config.jwks_url
    os.environ["AUTH__ALGORITHM"] = auth_users.token_algorithm
    os.environ["AUTH__JWT_AUDIENCE"] = "authenticated"

    import wurzel.api.backends.supabase.client as supabase_client  # noqa: PLC0415

    supabase_client._get_settings.cache_clear()
    supabase_client._async_client = None

    settings = APISettings(API_KEY=TEST_API_KEY)
    _app = create_app(settings=settings, otel_settings=OTELSettings(ENABLED=False))
    _app.dependency_overrides[_get_settings] = lambda: settings

    # Map tokens to user claims for JWT verification
    token_to_user = {
        auth_users.admin_token: UserClaims(sub=auth_users.admin_user_id, email="wurzel-e2e-admin@example.local", raw={}),
        auth_users.member_token: UserClaims(sub=auth_users.member_user_id, email="wurzel-e2e-member@example.local", raw={}),
        auth_users.secret_editor_token: UserClaims(
            sub=auth_users.secret_editor_user_id, email="wurzel-e2e-secret-editor@example.local", raw={}
        ),
        auth_users.viewer_token: UserClaims(sub=auth_users.viewer_user_id, email="wurzel-e2e-viewer@example.local", raw={}),
        auth_users.no_role_token: UserClaims(sub=auth_users.no_role_user_id, email="wurzel-e2e-no-role@example.local", raw={}),
    }

    _bearer = HTTPBearer(auto_error=False)

    async def mock_verify_jwt(credentials=Depends(_bearer)) -> UserClaims:  # noqa: PLC0415
        if credentials is None:
            from wurzel.api.error_codes import ErrorCode  # noqa: PLC0415

            raise ErrorCode.INVALID_TOKEN.error(detail="Authorization: Bearer <token> header is required.")
        token = credentials.credentials
        if token not in token_to_user:
            from wurzel.api.error_codes import ErrorCode  # noqa: PLC0415

            raise ErrorCode.TOKEN_VERIFICATION_FAILED.error(detail="JWT token is invalid or expired.")
        return token_to_user[token]

    _app.dependency_overrides[_verify_jwt] = mock_verify_jwt
    return _app


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def api_key_headers() -> dict[str, str]:
    return {"X-API-Key": TEST_API_KEY}


@pytest.fixture(scope="session")
def role_headers(auth_users: E2EAuthUsers) -> dict[str, dict[str, str]]:
    return {
        "admin": {"Authorization": f"Bearer {auth_users.admin_token}"},
        "member": {"Authorization": f"Bearer {auth_users.member_token}"},
        "secret_editor": {"Authorization": f"Bearer {auth_users.secret_editor_token}"},
        "viewer": {"Authorization": f"Bearer {auth_users.viewer_token}"},
        "no_role": {"Authorization": f"Bearer {auth_users.no_role_token}"},
    }


@pytest.fixture(scope="session")
def localstack_config() -> LocalStackConfig:
    endpoint = os.getenv("LOCALSTACK_URL", "http://127.0.0.1:4566")
    bucket_name = os.getenv("WURZEL_E2E_S3_BUCKET", "wurzel-e2e")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    try:
        with httpx.Client(timeout=5.0) as c:
            health = c.get(f"{endpoint}/_localstack/health")
            if health.status_code != 200:
                pytest.skip(f"LocalStack is not healthy at {endpoint}")
    except httpx.HTTPError:
        pytest.skip(f"LocalStack is not reachable at {endpoint}")
    return LocalStackConfig(endpoint_url=endpoint, bucket_name=bucket_name, region_name=region)


@pytest.fixture(scope="session")
def s3_file_service(localstack_config: LocalStackConfig):
    boto3 = pytest.importorskip("boto3", reason="boto3 is required for LocalStack S3 e2e tests")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("AWS_DEFAULT_REGION", localstack_config.region_name)

    service = S3FileStorageService(
        bucket_name=localstack_config.bucket_name,
        bucket_prefix="wurzel-e2e",
        region_name=localstack_config.region_name,
    )
    service._s3_client = boto3.client(  # pylint: disable=protected-access
        "s3",
        endpoint_url=localstack_config.endpoint_url,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=localstack_config.region_name,
    )
    try:
        service._s3_client.create_bucket(Bucket=localstack_config.bucket_name)  # pylint: disable=protected-access
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return service


@pytest.fixture
def s3_client(app, s3_file_service: S3FileStorageService):
    app.dependency_overrides[get_file_upload_service] = lambda: FileUploadService(s3_file_service)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_file_upload_service, None)


@pytest.fixture
def step_info_factory():
    def _factory(*, extensions: list[str] | None = None, mime_types: list[str] | None = None) -> Any:
        step_info = type("StepInfo", (), {})()
        step_info.accepted_file_extensions = extensions or []
        step_info.accepted_mime_types = mime_types or []
        return step_info

    return _factory


@pytest.fixture
def project_context(client, auth_users: E2EAuthUsers, role_headers: dict[str, dict[str, str]]) -> dict[str, str]:
    create_resp = client.post(
        "/v1/projects",
        json={"name": f"e2e-project-{uuid.uuid4().hex[:8]}", "description": "supabase-e2e"},
        headers=role_headers["admin"],
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    members = [
        (auth_users.member_user_id, "member"),
        (auth_users.secret_editor_user_id, "secret_editor"),
        (auth_users.viewer_user_id, "viewer"),
    ]
    for user_id, role in members:
        add_resp = client.post(
            f"/v1/projects/{project_id}/members",
            json={"user_id": user_id, "role": role},
            headers=role_headers["admin"],
        )
        assert add_resp.status_code == 201

    branch_resp = client.post(
        f"/v1/projects/{project_id}/branches",
        json={"name": "feature-a"},
        headers=role_headers["admin"],
    )
    assert branch_resp.status_code == 201

    manifest = {
        "apiVersion": "wurzel.dev/v1alpha1",
        "kind": "Pipeline",
        "metadata": {"name": f"pipeline-{uuid.uuid4().hex[:8]}"},
        "spec": {
            "backend": "dvc",
            "steps": [{"name": "source", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"}],
        },
    }
    manifest_resp = client.put(
        f"/v1/projects/{project_id}/branches/feature-a/manifest",
        json=manifest,
        headers=role_headers["admin"],
    )
    assert manifest_resp.status_code == 200

    return {"project_id": project_id, "feature_branch": "feature-a"}
