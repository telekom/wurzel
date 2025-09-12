# Getting Started

This guide covers setting up your development environment, understanding the development workflow, and running your first tests with Wurzel.


## Development Setup

### Prerequisites

Before starting, ensure you have completed the [installation process](installation.md). If you're setting up for development, you should have:

- Python 3.11 or 3.12
- Wurzel installed with development dependencies
- Pre-commit hooks configured

### Verify Your Installation

```bash
# Check that Wurzel is properly installed
python -c "import wurzel; print('Wurzel installed successfully')"

# Verify CLI access
wurzel --help

# Test that development tools are available
make --version
pre-commit --version
```

## Development Workflow

### Code Quality & Linting

Wurzel uses pre-commit hooks to enforce consistent code quality and formatting. These hooks run automatically on every commit to ensure code standards.

#### Set Up Pre-commit Hooks

If you used `make install`, pre-commit hooks are already configured. Otherwise, set them up manually:

```bash
pre-commit install
```

#### Run Linting Manually

You can trigger the linting process manually at any time:

```bash
make lint
```

This runs all configured linters and formatters across the codebase, including:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Style and error checking
- **mypy**: Type checking
- **Ruff**: Fast Python linter

### Running Tests

Before submitting changes, ensure all tests pass:

```bash
# Run the complete test suite
make test

# Run tests with coverage report
make test-coverage

# Run specific test files
python -m pytest tests/test_specific_file.py

# Run tests with verbose output
python -m pytest -v
```

#### Test Structure

Wurzel's test suite includes:

- **Unit tests**: Testing individual components
- **Integration tests**: Testing component interactions
- **End-to-end tests**: Testing complete pipeline flows

### Documentation

#### Local Documentation Development

Preview documentation changes locally:

```bash
# Serve documentation locally (auto-reloads on changes)
make documentation

# Build documentation without serving
mkdocs build
```

The documentation will be available at `http://127.0.0.1:8000/`

#### Documentation Structure

Wurzel uses MkDocs for documentation management:

- **Source files**: Located in `docs/`
- **Configuration**: `mkdocs.yml`
- **Auto-generated API docs**: Built from docstrings

## Development Guidelines

### Commit Strategy

Wurzel maintains a clean Git history through a structured commit strategy.

#### Commit Message Format

Follow this structure for commit messages:

```text
<tag>: <short description>

<longer description (optional)>
```

#### Commit Types

- **Breaking Changes**: For changes that are not backward-compatible
  - Use tag: `breaking`
- **Features**: For new features or enhancements that are backward-compatible
  - Use tags: `feat`, `feature`
- **Fixes and Improvements**: For bug fixes, performance improvements, or small patches
  - Use tags: `fix`, `hotfix`, `perf`, `patch`

#### Allowed Tags

Ensure consistency by using these approved tags:

- `feat`, `feature`, `fix`, `hotfix`, `perf`, `patch`
- `build`, `chore`, `ci`, `docs`, `style`, `refactor`, `ref`, `test`

#### Examples

```bash
# Good commit messages
git commit -m "feat: add semantic text splitter for German documents"
git commit -m "fix: resolve memory leak in embedding generation"
git commit -m "docs: update installation guide with Docker instructions"

# Bad commit messages
git commit -m "updated stuff"
git commit -m "fixed bug"
```

### Merge Strategy

- All commits are **squashed** when merging into the main branch
- This maintains a clean, readable project history
- Focus on meaningful commit messages during development

## Common Development Tasks

### Adding a New Feature

1. **Create a feature branch:**
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Implement your feature** following the [development guides](creating-steps.md)

3. **Add tests** for your feature:
   ```bash
   # Add tests in tests/ directory
   python -m pytest tests/test_your_feature.py
   ```

4. **Update documentation** if needed

5. **Run quality checks:**
   ```bash
   make lint
   make test
   ```

6. **Commit using proper format:**
   ```bash
   git commit -m "feat: add your feature description"
   ```

### Fixing a Bug

1. **Create a fix branch:**
   ```bash
   git checkout -b fix/bug-description
   ```

2. **Write a failing test** that reproduces the bug

3. **Implement the fix**

4. **Verify the test passes:**
   ```bash
   python -m pytest tests/test_bug_fix.py
   ```

5. **Run full test suite:**
   ```bash
   make test
   ```

### Working with Dependencies

#### Adding New Dependencies

1. **Add to pyproject.toml** in the appropriate section:
   ```toml
   dependencies = [
       "existing-package>=1.0.0",
       "new-package>=2.0.0",
   ]
   ```

2. **For optional dependencies:**
   ```toml
   [project.optional-dependencies]
   your-extra = ["optional-package>=1.0.0"]
   ```

3. **Update installation:**
   ```bash
   make install
   ```

#### Direct Dependencies

For packages that can't be installed via PyPI (like spaCy models):

1. **Add to DIRECT_REQUIREMENTS.txt:**
   ```
   https://github.com/explosion/spacy-models/releases/download/de_core_news_sm-3.7.0/de_core_news_sm-3.7.0-py3-none-any.whl
   ```

2. **Document in installation guide** if user-facing

## Debugging Tips

### Common Issues

#### Import Errors

```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Verify package installation
pip list | grep wurzel
```

#### Test Failures

```bash
# Run tests with detailed output
python -m pytest -v -s

# Run specific test method
python -m pytest tests/test_file.py::TestClass::test_method

# Debug with pdb
python -m pytest --pdb tests/test_file.py
```

#### Development Environment Issues

```bash
# Clean and reinstall
make clean
make install

# Verify pre-commit setup
pre-commit run --all-files
```

### Useful Development Commands

```bash
# Clean build artifacts
make clean

# Format code manually
black .
isort .

# Type checking
mypy wurzel/

# Check test coverage
coverage run -m pytest
coverage report
coverage html  # Generate HTML report
```

## Next Steps

Now that you have your development environment set up:

1. **[Build Your First Pipeline](building-pipelines.md)** - Learn core pipeline concepts
2. **[Create Custom Steps](creating-steps.md)** - Build your own processing components
3. **[Understand Data Contracts](data-contracts.md)** - Learn about type-safe data exchange
4. **[Explore Backends](../backends/index.md)** - Understand deployment options

## Additional Resources


- **[API Documentation](https://deepwiki.com/telekom/wurzel/)** - Auto-generated API reference
- **[Example Pipelines](https://github.com/telekom/wurzel/tree/main/examples)** - Real-world implementation examples
