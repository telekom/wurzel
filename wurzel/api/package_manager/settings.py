# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the runtime package manager."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from wurzel.core.settings import Settings


class PackageManagerSettings(Settings):
    r"""Configuration for runtime per-project package installation.

    All fields are read from environment variables with the prefix
    ``PACKAGE_MANAGER__``.

    Example::

        PACKAGE_MANAGER__PACKAGES_DIR=/mnt/packages \\
        PACKAGE_MANAGER__UV_EXECUTABLE=/usr/local/bin/uv \\
        uvicorn wurzel.api.app:create_app --factory
    """

    model_config = SettingsConfigDict(
        env_prefix="PACKAGE_MANAGER__",
        extra="ignore",
        case_sensitive=True,
    )

    PACKAGES_DIR: Path = Field(
        ...,
        description=("Path to the shared volume where per-project packages are installed. Must be the same mount path on every replica."),
    )
    UV_EXECUTABLE: str = Field(
        "uv",
        description="Path (or name) of the uv binary used to install packages.",
    )
    INSTALLER_ID: str = Field(
        default_factory=lambda: str(uuid4()),
        description=("Unique identifier for this API replica. Used as a distributed lock token when claiming package installs."),
    )
    INSTALLING_TIMEOUT_SECONDS: int = Field(
        300,
        gt=0,
        description=(
            "Seconds after which a package stuck in 'installing' status (e.g. from a crashed replica) is reset to 'pending' on startup."
        ),
    )
