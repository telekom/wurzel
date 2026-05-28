# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Package installation helpers.

Wraps ``uv pip install --target`` and reads the resulting ``.dist-info/RECORD``
files to produce a reproducible lock entry list.
"""

from __future__ import annotations

import csv
import logging
import re
import subprocess
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Conservative PEP 508 name pattern — allows letters, digits, hyphens, dots,
# underscores, brackets (extras), and common version specifiers.
# Rejects shell metacharacters.  Defence-in-depth even though shell=False.
_PEP508_RE = re.compile(
    r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?"  # distribution name
    r"(\[[A-Za-z0-9,._-]+\])?"  # optional extras
    r"(\s*[><=!~^]{1,3}\s*[A-Za-z0-9.*+!-]+(\s*,\s*[><=!~^]{1,3}\s*[A-Za-z0-9.*+!-]+)*)?"  # optional version specifier(s)
    r"(@\s*\S+)?$"  # optional URL (PEP 440 direct references)
)


def validate_package_spec(package_spec: str) -> None:
    """Raise :exc:`ValueError` if *package_spec* contains unsafe characters.

    Args:
        package_spec: PEP 508 dependency specifier.

    Raises:
        ValueError: If the spec does not match the allowed pattern.
    """
    if not _PEP508_RE.match(package_spec.strip()):
        raise ValueError(f"Invalid package spec {package_spec!r}. Only PEP 508 names with optional version specifiers are allowed.")


def get_project_package_dir(project_id: uuid.UUID, packages_dir: Path) -> Path:
    """Return the target directory for *project_id*'s installed packages.

    Args:
        project_id: Project UUID.
        packages_dir: Root directory for all per-project packages (shared volume).

    Returns:
        Path of the form ``<packages_dir>/<project_id>/``.
    """
    return packages_dir / str(project_id)


def install_package(
    project_id: uuid.UUID,
    package_spec: str,
    index_url: str | None,
    packages_dir: Path,
    uv_executable: str,
) -> None:
    """Install *package_spec* into the project's target directory using uv.

    Args:
        project_id: Project UUID — determines the target directory.
        package_spec: PEP 508 dependency specifier (already validated).
        index_url: Optional private PyPI index URL (including credentials).
                   Resolved from ``project_secrets`` by the caller; never stored
                   in ``project_packages``.
        packages_dir: Root directory for all per-project packages.
        uv_executable: Path or name of the ``uv`` binary.

    Raises:
        RuntimeError: If ``uv`` exits with a non-zero status code.
    """
    target_dir = get_project_package_dir(project_id, packages_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        uv_executable,
        "pip",
        "install",
        "--target",
        str(target_dir),
        package_spec,
    ]
    if index_url:
        cmd.extend(["--index-url", index_url])

    logger.info("Installing %r for project %s → %s", package_spec, project_id, target_dir)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        raise RuntimeError(f"uv install failed for {package_spec!r} (exit {result.returncode}):\n{result.stderr}")
    logger.info("Installed %r for project %s", package_spec, project_id)


def read_lock_entries(target_dir: Path) -> list[dict[str, str]]:
    """Scan ``target_dir`` for ``.dist-info/RECORD`` files and return lock entries.

    Each installed distribution contributes exactly one entry, using the
    SHA-256 hash of the wheel file recorded in its RECORD (PEP 376 / PEP 627).

    Args:
        target_dir: The ``--target`` directory passed to ``uv pip install``.

    Returns:
        List of ``{"requirement": "pkgname==version", "sha256": "<hex>"}``
        dicts, one per installed distribution.  Empty if no RECORD files found.
    """
    entries: list[dict[str, str]] = []
    for record_file in target_dir.glob("*.dist-info/RECORD"):
        dist_info_dir = record_file.parent
        # Extract name and version from the directory name, e.g. "httpx-0.27.0.dist-info"
        dist_info_name = dist_info_dir.name  # e.g. "httpx-0.27.0.dist-info"
        stem = dist_info_name[: -len(".dist-info")]
        # stem may be "httpx-0.27.0" or "my_pkg-1.0.0"
        parts = stem.rsplit("-", 1)
        if len(parts) != 2:
            logger.debug("Skipping unexpected dist-info dir: %s", dist_info_dir)
            continue
        pkg_name, pkg_version = parts
        requirement = f"{pkg_name}=={pkg_version}"

        sha256: str | None = None
        try:
            with record_file.open(newline="") as fh:
                reader = csv.reader(fh)
                for row in reader:
                    # RECORD format: path,hash,size  — hash is "sha256:<hex>" or empty
                    if len(row) >= 2 and row[1].startswith("sha256:"):
                        sha256 = row[1][len("sha256:") :]
                        break
        except OSError:
            logger.debug("Could not read RECORD file: %s", record_file)
            continue

        if sha256:
            entries.append({"requirement": requirement, "sha256": sha256})
        else:
            logger.debug("No SHA-256 hash found in RECORD for %s", requirement)

    return entries
