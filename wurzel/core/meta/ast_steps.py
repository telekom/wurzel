# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""AST-based TypedStep discovery utilities.

Finds TypedStep subclasses by parsing Python source files without importing
them — safe for API servers and completion engines where importing arbitrary
code is undesirable.
"""

from __future__ import annotations

import ast
import logging
from importlib.metadata import distributions
from importlib.util import find_spec
from pathlib import Path

logger = logging.getLogger(__name__)

_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        ".tox",
        ".pytest_cache",
        "build",
        "dist",
    }
)

# Exclude internal wurzel framework classes from discovery results
_EXCLUDE_CLASS_PATHS: frozenset[str] = frozenset(
    {
        "wurzel.core.self_consuming_step.SelfConsumingLeafStep",
    }
)

# Module-level cache for wurzel-dependent packages
# Built on first use, avoids repeated distributions() calls
_WURZEL_DEPENDENT_PACKAGES_CACHE: set[str] | None = None


def check_if_typed_step(node: ast.ClassDef) -> bool:
    """Return True if the AST class node directly inherits from TypedStep."""
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "TypedStep":
            return True
        if isinstance(base, ast.Subscript):
            if isinstance(base.value, ast.Name) and base.value.id == "TypedStep":
                return True
            if isinstance(base.value, ast.Attribute) and base.value.attr == "TypedStep":
                return True
        if isinstance(base, ast.Attribute) and base.attr == "TypedStep":
            return True
    return False


def _get_wurzel_dependent_packages() -> set[str]:
    """Get all installed packages that depend on wurzel.

    Uses caching to avoid repeated distribution calls. Only scans packages that
    actually depend on wurzel, which is much faster than scanning all packages
    and filtering by keywords.

    Returns:
        Set of package names (normalized: hyphens -> underscores) that depend on wurzel
    """
    global _WURZEL_DEPENDENT_PACKAGES_CACHE  # pylint: disable=global-statement

    if _WURZEL_DEPENDENT_PACKAGES_CACHE is not None:
        return _WURZEL_DEPENDENT_PACKAGES_CACHE

    try:
        wurzel_deps = set()

        for dist in distributions():
            requires = dist.requires or []
            for req in requires:
                # Parse requirement string (e.g., "wurzel>=1.0", "wurzel[extra]>=1.0")
                # Extract just the package name before any operators or brackets
                req_pkg = req.split(";")[0]  # Remove environment markers
                req_pkg = req_pkg.split(">")[0]  # Remove >
                req_pkg = req_pkg.split("<")[0]  # Remove <
                req_pkg = req_pkg.split("=")[0]  # Remove =
                req_pkg = req_pkg.split("[")[0]  # Remove extras
                req_pkg = req_pkg.split("!")[0]  # Remove !=
                req_pkg = req_pkg.strip()

                if req_pkg.lower() == "wurzel":
                    # Normalize package name: hyphens to underscores
                    normalized_name = dist.name.replace("-", "_")
                    wurzel_deps.add(normalized_name)
                    break

        _WURZEL_DEPENDENT_PACKAGES_CACHE = wurzel_deps
        logger.debug(f"Found {len(wurzel_deps)} packages depending on wurzel")
        return wurzel_deps

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.debug(f"Failed to get wurzel-dependent packages: {e}")
        return set()


def build_module_path(py_file: Path, search_path: Path, base_module: str) -> str:
    """Return a dotted module path for py_file relative to search_path."""
    rel_path = py_file.relative_to(search_path)
    path_parts = list(rel_path.parts[:-1]) + [rel_path.stem]
    if base_module:
        return f"{base_module}.{'.'.join(path_parts)}"
    return ".".join(path_parts) if path_parts else rel_path.stem


def scan_path_for_typed_steps(search_path: Path, base_module: str = "") -> list[str]:
    """AST-scan *search_path* and return fully-qualified class paths of TypedStep subclasses.

    Files are never imported; only their source text is parsed.
    """
    results: list[str] = []
    for py_file in search_path.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        if _EXCLUDE_DIRS.intersection(py_file.parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            if "TypedStep" not in content:
                continue
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and check_if_typed_step(node):
                    try:
                        module_path = build_module_path(py_file, search_path, base_module)
                        results.append(f"{module_path}.{node.name}")
                    except ValueError:
                        continue
        except (OSError, SyntaxError, UnicodeDecodeError):
            pass
    return results


def find_typed_steps_in_venv() -> list[str]:
    """Return fully-qualified class paths of all TypedStep subclasses in the current venv.

    Enumerates installed distributions via :mod:`importlib.metadata` and
    AST-scans each one without importing any code.
    """
    # Use an insertion-ordered dict as a deduplication set.
    seen: dict[str, None] = {}
    seen_roots: set[Path] = set()

    for dist in distributions():
        top_level_text = dist.read_text("top_level.txt")
        if top_level_text:
            top_pkgs = [p.strip() for p in top_level_text.splitlines() if p.strip() and not p.strip().startswith("_")]
        else:
            top_pkgs = [dist.name.replace("-", "_")]

        for pkg_name in top_pkgs:
            try:
                spec = find_spec(pkg_name)
                if spec is None:
                    continue
                if spec.submodule_search_locations:
                    pkg_root = Path(list(spec.submodule_search_locations)[0])
                elif spec.origin and spec.origin.endswith("__init__.py"):
                    # Namespace package with only an __init__.py — treat its dir as root
                    pkg_root = Path(spec.origin).parent
                else:
                    # Single-file module (e.g. threadpoolctl.py) — scanning its parent
                    # directory would pick up unrelated packages.  Skip it.
                    continue

                resolved = pkg_root.resolve()
                if resolved in seen_roots:
                    continue
                seen_roots.add(resolved)

                for class_path in scan_path_for_typed_steps(pkg_root, pkg_name):
                    seen.setdefault(class_path, None)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.debug("Could not scan package %s", pkg_name, exc_info=True)
                continue

    return list(seen)


def find_typed_steps_from_wurzel_dependents() -> list[str]:
    """Return TypedStep subclasses from packages that depend on wurzel.

    Filtered discovery for CLI/UI use cases where only wurzel-ecosystem steps
    should be shown. Excludes internal wurzel framework classes.

    Returns:
        Fully-qualified class paths of TypedStep subclasses from wurzel-dependent packages,
        excluding framework classes.
    """
    # Use an insertion-ordered dict as a deduplication set.
    seen: dict[str, None] = {}
    seen_roots: set[Path] = set()

    # Only scan packages that actually depend on wurzel
    wurzel_deps = _get_wurzel_dependent_packages()

    for pkg_name in wurzel_deps:
        try:
            spec = find_spec(pkg_name)
            if spec is None:
                continue
            if spec.submodule_search_locations:
                pkg_root = Path(list(spec.submodule_search_locations)[0])
            elif spec.origin and spec.origin.endswith("__init__.py"):
                # Namespace package with only an __init__.py — treat its dir as root
                pkg_root = Path(spec.origin).parent
            else:
                # Single-file module — skip it
                continue

            resolved = pkg_root.resolve()
            if resolved in seen_roots:
                continue
            seen_roots.add(resolved)

            for class_path in scan_path_for_typed_steps(pkg_root, pkg_name):
                # Exclude framework classes (both specific exclusions and wurzel.core.*)
                if class_path not in _EXCLUDE_CLASS_PATHS and not class_path.startswith("wurzel.core."):
                    seen.setdefault(class_path, None)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.debug("Could not scan package %s", pkg_name, exc_info=True)
            continue

    return list(seen)
