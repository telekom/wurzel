<!--
SPDX-FileCopyrightText: 2024 Deutsche Telekom AG

SPDX-License-Identifier: CC0-1.0
-->
# Contributing to Wurzel

We welcome contributions to Wurzel! Whether you're adding new features, improving documentation, or fixing bugs, your help is greatly appreciated.

## Development Installation
If you want to contribute to Wurzel, you can set up the development environment as follows:

```bash
git clone https://github.com/telekom/wurzel/
cd wurzel

# Creates a new virtual environment and installs all dependencies
make install
```

## Running Tests
Before submitting your changes, ensure all tests pass by running:

```bash
make test
```

This ensures that your modifications do not break the package. The CI pipeline also runs these tests automatically.

## Running Linting
To check for code style and formatting issues before making a pull request, run:

```bash
make lint
```

This command enforces consistency and prevents formatting-related errors.

## Submitting Contributions
1. Fork the repository and create a new branch for your changes.
2. Make your modifications and commit them with clear commit messages.
3. Ensure all tests and linting checks pass.
4. Open a pull request (PR) against the `main` branch, describing your changes.

## Semantic Versioning
Wurzel follows [semantic versioning](https://semver.org/). Commit prefixes help manage version bumps automatically:

- `fix:` for patches
- `feat:` for new features (minor versions)
- `breaking:` for breaking changes (major versions)

Other prefixes like `docs:`, `chore:`, and `refactor:` help structure the commit history but do not trigger a version bump.
## Commit Message Guidelines

Wurzel uses [semantic-release](https://semantic-release.gitbook.io/semantic-release/) to automate versioning and package publishing. To ensure your commits trigger the correct version updates, follow these guidelines:

The [`pyproject.toml`](./pyproject.toml) file specifies the allowed commit types under `[tool.semantic_release.commit_parser_options]`.

```toml
major_types = ["breaking"]
minor_types = ["feat"]
patch_types = ["fix", "perf"]
allowed_tags = ["feat", "fix", "perf", "build", "chore", "ci", "docs", "style", "refactor", "ref", "test"]
```
This means that the version number of the package is composed of three numbers: `MAJOR.MINOR.PATCH`. This allow us to use existing tools to automatically manage the versioning of the package.

Any commit with one of these prefixes will trigger a version bump upon merging to the main branch as long as tests pass. A version bump will then trigger a new release on PyPI as well as a new release on GitHub.

Ensure your commit messages follow the format `type: description`.

Thank you for contributing to Wurzel!
