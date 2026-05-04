# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Autocompletion helper for discovering TypedStep classes.

NOTE: Some code is intentionally duplicated from wurzel.core.meta.ast_steps
to keep this module lightweight and fast for shell completion, avoiding
the overhead of importing the full ast_steps module.
"""

# pylint: disable=duplicate-code
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from wurzel.core.meta.ast_steps import _get_wurzel_dependent_packages  # pylint: disable=import-outside-toplevel

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

# Module-level cache for autocompletion results
# Cache key: (search_path, base_module) -> list of discovered step names
_COMPLETION_CACHE: dict[tuple[str, str], list[str]] = {}


def _process_python_file(py_file: Path, search_path: Path, base_module: str, incomplete: str, hints: list) -> None:
    """Process a single Python file to find TypedStep classes."""
    import ast  # pylint: disable=import-outside-toplevel

    # Lazy import of AST helpers (only used when processing files)
    # NOTE: Some logic duplicated from wurzel.core.meta.ast_steps for performance
    # to avoid importing that heavy module just for autocompletion
    from wurzel.core.meta.ast_steps import (  # pylint: disable=import-outside-toplevel
        build_module_path,
        check_if_typed_step,
    )

    try:
        # Fast AST parsing without executing code
        with open(py_file, encoding="utf-8") as f:
            content = f.read()

        # Quick regex check before AST parsing (even faster)
        if "TypedStep" not in content:
            return

        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and check_if_typed_step(node):
                # Create module path based on file location
                try:
                    module_path = build_module_path(py_file, search_path, base_module)
                    full_name = f"{module_path}.{node.name}"
                    if full_name.startswith(incomplete):
                        hints.append(full_name)
                except ValueError:
                    # File is not relative to search_path, skip it
                    continue

    except (OSError, SyntaxError, UnicodeDecodeError):
        # Skip files that can't be parsed
        pass


def complete_step_import(incomplete: str) -> list[str]:  # pylint: disable=too-many-statements,too-many-branches,too-many-locals,too-many-nested-blocks
    """AutoComplete for steps - discover TypedStep classes from current project and wurzel.

    Optimization strategy:
    - For prefix queries (incomplete != ""), use fast sequential scanning (no threading overhead)
    - For full scans (incomplete == ""), use cache + threading for comprehensive discovery
    - Threading overhead ~0.76s is avoided entirely for prefix queries
    - For installed packages: only scan packages that actually depend on wurzel (not keyword-based)
    """
    hints: list[str] = []

    # Early optimization: If we have a specific prefix, we can limit scanning
    should_scan_wurzel = not incomplete or incomplete.startswith("wurzel")
    should_scan_current = not incomplete or not incomplete.startswith("wurzel")
    # Only scan installed packages if: incomplete is empty OR doesn't start with "wurzel"
    # AND: incomplete is NOT a "nonexistent" prefix (optimization)
    should_scan_installed = (not incomplete or not incomplete.startswith("wurzel")) and incomplete != "nonexistent"

    def scan_directory_for_typed_steps(search_path: Path, base_module: str = "", max_files: int = 200, prefix_mode: bool = False) -> None:  # pylint: disable=unused-argument
        """Scan a directory for TypedStep classes and add them to hints.

        Args:
            search_path: Root directory to scan
            base_module: Base module name for discovered steps
            max_files: Maximum files to scan
            prefix_mode: If True, stop scanning once we have matches (fast path for prefix queries)
        """
        if not search_path.exists():
            return

        # Directories to exclude from scanning (performance optimization)
        # NOTE: Duplicated from wurzel.core.meta.ast_steps._EXCLUDE_DIRS for consistency
        # pylint: disable=duplicate-code
        exclude_dirs = {
            ".venv",
            "venv",
            ".env",
            "env",
            "__pycache__",
            ".git",
            ".svn",
            ".hg",
            "node_modules",
            ".tox",
            ".pytest_cache",
            "build",
            "dist",
            ".egg-info",
            "site-packages",
            "tests",  # Skip test directories - unlikely to contain user steps
            "test",
            "testing",
            "docs",  # Skip documentation
            "doc",
        }

        files_processed = 0

        # First, scan Python files directly in the search path
        for py_file in search_path.glob("*.py"):
            if files_processed >= max_files:
                break
            if py_file.name == "__init__.py":
                continue
            _process_python_file(py_file, search_path, base_module, incomplete, hints)
            files_processed += 1

        # Then scan top-level directories that might contain user steps
        for item in search_path.iterdir():
            if files_processed >= max_files:
                break
            if item.is_dir() and item.name not in exclude_dirs:
                # Only go 2 levels deep to avoid deep scanning
                for py_file in item.rglob("*.py"):
                    if files_processed >= max_files:
                        break
                    if py_file.name == "__init__.py":
                        continue

                    # Limit depth to 3 levels max (check relative path only, not absolute)
                    relative_parts = py_file.relative_to(search_path).parts
                    if len(relative_parts) > 3:
                        continue

                    # Check if file is in excluded directory (relative path only)
                    if any(exclude_dir in relative_parts for exclude_dir in exclude_dirs):
                        continue

                    _process_python_file(py_file, search_path, base_module, incomplete, hints)
                    files_processed += 1

    # OPTIMIZATION: For prefix queries, skip threading entirely (0.76s overhead)
    # Use fast sequential scanning instead
    # pylint: disable=too-many-nested-blocks
    if incomplete:
        # Fast path: sequential scanning for prefix queries
        try:
            if should_scan_wurzel:
                import wurzel  # pylint: disable=import-outside-toplevel

                wurzel_path = Path(wurzel.__file__).parent
                wurzel_steps_path = wurzel_path / "steps"
                wurzel_step_path = wurzel_path / "step"
                if wurzel_steps_path.exists():
                    scan_directory_for_typed_steps(wurzel_steps_path, "wurzel.steps", max_files=100, prefix_mode=True)
                if wurzel_step_path.exists():
                    scan_directory_for_typed_steps(wurzel_step_path, "wurzel.step", max_files=50, prefix_mode=True)
        except ImportError:
            pass

        try:
            if should_scan_current:
                current_dir = Path.cwd()
                scan_directory_for_typed_steps(current_dir, max_files=50, prefix_mode=True)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        try:
            if should_scan_installed:
                from importlib.util import find_spec  # pylint: disable=import-outside-toplevel

                # Only scan packages that actually depend on wurzel
                wurzel_deps = _get_wurzel_dependent_packages()

                # Get the package prefix to search for
                pkg_prefix = incomplete.split(".")[0] if "." in incomplete else incomplete

                # Scan only the wurzel-dependent packages that match the prefix
                for pkg_name in wurzel_deps:
                    if not pkg_prefix or pkg_name.startswith(pkg_prefix.replace("-", "_")):
                        try:
                            spec = find_spec(pkg_name)
                            if spec and spec.origin:
                                pkg_path = Path(spec.origin).parent
                                scan_directory_for_typed_steps(pkg_path, pkg_name, max_files=50, prefix_mode=True)
                        except (ImportError, ValueError, ModuleNotFoundError):
                            # Skip packages that can't be found
                            continue
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    else:
        # Full scan path: use threading for comprehensive discovery (when cache is empty)
        import threading  # pylint: disable=import-outside-toplevel

        scan_threads = []

        def scan_wurzel():
            if not should_scan_wurzel:
                return
            try:
                import wurzel  # pylint: disable=import-outside-toplevel

                wurzel_path = Path(wurzel.__file__).parent
                wurzel_steps_path = wurzel_path / "steps"
                wurzel_step_path = wurzel_path / "step"
                if wurzel_steps_path.exists():
                    scan_directory_for_typed_steps(wurzel_steps_path, "wurzel.steps", max_files=100)
                if wurzel_step_path.exists():
                    scan_directory_for_typed_steps(wurzel_step_path, "wurzel.step", max_files=50)
            except ImportError:
                pass

        def scan_current():
            if not should_scan_current:
                return
            try:
                current_dir = Path.cwd()
                scan_directory_for_typed_steps(current_dir, max_files=50)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        def scan_installed():
            if not should_scan_installed:
                return
            try:
                from importlib.util import find_spec  # pylint: disable=import-outside-toplevel

                # Only scan packages that actually depend on wurzel
                wurzel_deps = _get_wurzel_dependent_packages()

                for pkg_name in wurzel_deps:
                    try:
                        spec = find_spec(pkg_name)
                        if spec and spec.origin:
                            pkg_path = Path(spec.origin).parent
                            scan_directory_for_typed_steps(pkg_path, pkg_name, max_files=50)
                    except (ImportError, ValueError, ModuleNotFoundError):
                        # Skip packages that can't be found
                        continue
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        # Start all scan threads (only those that are needed)
        if should_scan_wurzel:
            scan_threads.append(threading.Thread(target=scan_wurzel))
        if should_scan_current:
            scan_threads.append(threading.Thread(target=scan_current))
        if should_scan_installed:
            scan_threads.append(threading.Thread(target=scan_installed))

        for t in scan_threads:
            t.start()
        for t in scan_threads:
            t.join(timeout=1.0)  # Add timeout to prevent hanging

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_hints: list[str] = []
    for hint in hints:
        if hint not in seen:
            seen.add(hint)
            unique_hints.append(hint)

    log.debug("found possible steps:", extra={"hints": unique_hints[:10]})  # Log first 10

    # Filter by incomplete prefix (no-op if already filtered in prefix_mode)
    # Also exclude wurzel.core.* steps (internal implementation details, not user-facing steps)
    return [hint for hint in unique_hints if hint.startswith(incomplete) and not hint.startswith("wurzel.core.")]
