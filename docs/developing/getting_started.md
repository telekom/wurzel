# 👩‍💻 Developer Guide

Welcome to the Wurzel Developer Guide! This document provides the essential steps and best practices to help you contribute effectively to the Wurzel project.

## 🚀 Getting Started

To install Wurzel with all necessary dependencies, run:

```bash
make install
```

This will install the core library along with all optional extras used for development, testing, and documentation.

## 🧼 Code Quality: Linting

Wurzel uses pre-commit hooks to enforce consistent code quality and formatting.

### ✅ Set Up Pre-commit Hooks

To activate the hooks:

```bash
pre-commit install
```

## 🧪 Run Linting Manually

You can also trigger the linting process manually using:

```bash
make lint
```

This runs all configured linters and formatters across the codebase.

## 🧪 Running Tests

Before submitting your changes, make sure all tests pass:

```bash
make test
```

This runs the full test suite and ensures your changes don’t break existing functionality.

## 📝 Commit Strategy

We maintain a clean and readable Git history by squashing all commits when merging into the main branch.

### 🔖 Commit Types

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
