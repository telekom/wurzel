# Developer Guide

Welcome to the Wurzel Developer Guide! This document provides essential information to help you get started with contributing to the project.


To get started with Wurzel, install the library using pip:

```bash
pip install "wurzel[all]"
```

## Linting

This project utilizes pre-commit hooks to ensure code quality. You can activate them to be run by default with the following command:

```bash
pre-commit install
```

You can run the linting process with the following command:

```bash
make lint
```

## Running Tests

Before submitting your changes, ensure all tests pass by running:

```bash
make test
```

## Commit Strategy

This section describes the commit strategy used in the project. All commits are squashed when merging into the `main` branch to maintain a clean and concise history.

### Commit Types
- **Breaking Changes**: For changes that are not backward-compatible.
    - Use the tag: `breaking`
- **Features**: For new features or enhancements that are backward-compatible.
    - Use the tags: `feat`, `feature`
- **Fixes and Improvements**: For bug fixes, performance improvements, or small patches.
    - Use the tags: `fix`, `perf`, `hotfix`, `patch`

### Allowed Tags
To ensure consistency, the following tags are allowed in commit messages:
- `feat`, `feature`, `fix`, `hotfix`, `perf`, `patch`, `build`, `chore`, `ci`, `docs`, `style`, `refactor`, `ref`, `test`

### Commit Message Format
Commit messages should follow this structure:
```
<tag>: <short description>

<longer description (optional)>
```

Adhering to this format ensures clarity and improves the readability of the project's history.
