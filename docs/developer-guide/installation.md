# Installation & Setup

This comprehensive guide covers installing Wurzel and setting up your development environment, including handling special dependencies and various deployment options.


## Basic Installation

### Prerequisites

- Python 3.11 or 3.12
- pip (Python package installer)
- Virtual environment (recommended)

### Quick Install

To get started with Wurzel, install the library using pip:

```bash
pip install wurzel
```

## Development Installation

For development work, we recommend using the provided Makefile which handles all dependencies:

```bash
# Clone the repository
git clone https://github.com/telekom/wurzel.git
cd wurzel

# Install all dependencies including development tools
make install
```

This installs:

- Core Wurzel library
- All optional dependencies
- Development tools (linting, testing, documentation)
- Pre-commit hooks setup

### Manual Development Setup

If you prefer manual installation:

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with all extras
pip install -e .[all,lint,test,docs]

# Install direct dependencies (see below)
pip install -r DIRECT_REQUIREMENTS.txt

# Set up pre-commit hooks
pre-commit install
```

## Direct Dependencies

Due to PyPI restrictions on direct dependencies, some components require manual installation. This primarily affects the German spaCy model used for semantic text splitting.

> ℹ️ **Why Direct Dependencies?** PyPI has restrictions on packages that include direct dependencies to external URLs for security reasons. The spaCy German model is hosted on GitHub releases rather than PyPI, requiring manual installation.

### Manual Installation

If you plan to use the semantic text splitting functionality (e.g., `SemanticSplitter`), you'll need to manually install the German spaCy model:

```bash
pip install https://github.com/explosion/spacy-models/releases/download/de_core_news_sm-3.7.0/de_core_news_sm-3.7.0-py3-none-any.whl
```

### Using DIRECT_REQUIREMENTS.txt

If you're working with the source code, you can install from the provided requirements file:

```bash
pip install -r DIRECT_REQUIREMENTS.txt
```

## Optional Dependencies

Wurzel supports various optional features through extras. You can install only what you need for your specific use case.

### Vector Database Support

```bash
# For Qdrant vector database
pip install wurzel[qdrant]

# For Milvus vector database
pip install wurzel[milvus]
```

### Document Processing

```bash
# For PDF document processing with Docling
pip install wurzel[docling]
```

### Backend Support

```bash
# For Argo Workflows backend
pip install wurzel[argo]
```

### Development Tools

```bash
# For linting and code quality tools
pip install wurzel[lint]

# For testing framework and tools
pip install wurzel[test]

# For documentation generation
pip install wurzel[docs]
```

### Install Everything

```bash
# Install all optional dependencies
pip install wurzel[all]

# Don't forget the direct dependencies!
pip install -r DIRECT_REQUIREMENTS.txt
```

## Docker Installation

The Docker image includes all dependencies automatically and is the easiest way to get started:

```bash
# Pull the latest image
docker pull ghcr.io/telekom/wurzel:latest

# Or build locally
docker build -t wurzel .
```

### Running with Docker

```bash
docker run \
  -e GIT_USER=wurzel-demo \
  -e GIT_MAIL=demo@example.com \
  -e DVC_DATA_PATH=/usr/app/data \
  -e DVC_FILE=/usr/app/dvc.yaml \
  -e WURZEL_PIPELINE=pipelinedemo:pipeline \
  ghcr.io/telekom/wurzel:latest
```

## Environment Configuration

When running Wurzel, several environment variables can be configured to customize behavior:

### Git Configuration

- `GIT_USER`: Git username for repository operations (default: `wurzel`)
- `GIT_MAIL`: Git email for repository operations (default: `wurzel@example.com`)

### DVC Configuration

- `DVC_DATA_PATH`: Path where DVC stores data files (default: `/usr/app/dvc-data`)
- `DVC_FILE`: Path to the DVC pipeline definition file (default: `/usr/app/dvc.yaml`)
- `DVC_CACHE_HISTORY_NUMBER`: Number of cache versions to keep (default: `30`)

### Pipeline Configuration

- `WURZEL_PIPELINE`: Specifies which pipeline to execute (e.g., `pipelinedemo:pipeline`)

### Monitoring (Optional)

- `PROMETHEUS__GATEWAY`: Prometheus pushgateway URL for metrics

For backend-specific configuration, see:

- **[DVC Backend Configuration](../backends/dvc.md#environment-configuration)**
- **[Argo Backend Configuration](../backends/argoworkflows.md#environment-configuration)**

## Verification

### Verify Basic Installation

```bash
# Check Wurzel installation
python -c "import wurzel; print('Wurzel installed successfully')"

# Check CLI is available
wurzel --help
```

### Verify spaCy Model

```bash
# Test spaCy model loading
python -c "import spacy; nlp = spacy.load('de_core_news_sm'); print('spaCy model loaded successfully')"
```

### Run Tests

```bash
# Run the test suite
make test

# Or manually
python -m pytest
```

## Troubleshooting

### Common Issues

#### spaCy Model Issues

If you encounter issues with the spaCy model:

1. **Verify the model is installed:**

   ```bash
   python -c "import spacy; nlp = spacy.load('de_core_news_sm'); print('Model loaded successfully')"
   ```

2. **Reinstall the model if needed:**

   ```bash
   pip uninstall de-core-news-sm
   pip install https://github.com/explosion/spacy-models/releases/download/de_core_news_sm-3.7.0/de_core_news_sm-3.7.0-py3-none-any.whl
   ```

#### Environment Issues

- **Python Version**: Ensure you're using Python 3.11 or 3.12
- **Virtual Environment**: Always use a virtual environment to avoid conflicts:

  ```bash
  python -m venv .venv
  source .venv/bin/activate  # On Windows: .venv\Scripts\activate
  pip install wurzel
  ```

#### Dependency Conflicts

- **Clean Installation**: Start with a fresh virtual environment
- **Upgrade pip**: Ensure you have the latest pip version:

  ```bash
  python -m pip install --upgrade pip
  ```

### Getting Help

If you encounter issues not covered here:

1. Check the [examples directory](../examples/) for working configurations
2. Review the [API documentation](https://deepwiki.com/telekom/wurzel/)
3. Consult the [troubleshooting section](../backends/introduction.md) in backend documentation
4. Open an issue on the [GitHub repository](https://github.com/telekom/wurzel)

## Next Steps

Once you have Wurzel installed:

1. **[Get Started with Development](getting-started.md)** - Set up your development workflow
2. **[Build Your First Pipeline](building-pipelines.md)** - Learn the core concepts
3. **[Explore Backends](../backends/introduction.md)** - Understand deployment options

## Additional Resources

- **[Backend Configuration](../backends/)** - Platform-specific deployment guides
- **[Contributing Guidelines](../CONTRIBUTING.md)** - How to contribute to Wurzel
- **[PyPI Direct Dependencies Documentation](https://packaging.python.org/specifications/core-metadata/)** - Understanding PyPI limitations
