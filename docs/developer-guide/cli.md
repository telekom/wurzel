<!--
SPDX-FileCopyrightText: 2025 Deutsche Telekom AG

SPDX-License-Identifier: CC0-1.0
-->

# 🖥️ Wurzel CLI Reference

The Wurzel CLI provides a powerful command-line interface for managing and executing ETL pipelines for RAG systems.

## Quick Start

```bash
# Install wurzel
pip install wurzel

# Run a step
wurzel run wurzel.steps.manual_markdown.ManualMarkdownStep --inputs ./data --output ./out

# Inspect a step
wurzel inspect wurzel.steps.manual_markdown.ManualMarkdownStep

# Generate a pipeline
wurzel generate examples.pipeline.pipelinedemo.pipeline
```

## Glossary

### PIPELINE { #PIPELINE data-toc-label="PIPELINE" }

Module path to a chained pipeline (multiple steps combined with the `>>` operator). Example: `examples.pipeline.pipelinedemo.pipeline`

## CLI Commands Reference

The following documentation is automatically generated from the Wurzel CLI code:

::: mkdocs-typer2
    :module: wurzel.cli._main
    :name: wurzel

## Usage Examples

### Running Steps

```bash
# Basic usage
wurzel run wurzel.steps.manual_markdown.ManualMarkdownStep \
    --inputs ./markdown-files \
    --output ./processed-output

# With middlewares (e.g., prometheus metrics)
wurzel run wurzel.steps.manual_markdown.ManualMarkdownStep \
    --inputs ./markdown-files \
    --output ./processed-output \
    --middlewares prometheus

# Multiple input folders
wurzel run wurzel.steps.splitter.SimpleSplitterStep \
    --inputs ./docs \
    --inputs ./markdown \
    --inputs ./pdfs \
    --output ./split-output
```

### Inspecting Steps

```bash
# Basic inspection
wurzel inspect wurzel.steps.manual_markdown.ManualMarkdownStep

# Generate environment file
wurzel inspect wurzel.steps.manual_markdown.ManualMarkdownStep --gen-env
```

### Managing Environment Variables

Use the `wurzel env` helper to inspect or validate the variables your pipeline needs:

```bash
# Show required env vars (toggle optional ones via --only-required)
wurzel env examples.pipeline.pipelinedemo:pipeline --only-required

# Generate a .env snippet with defaults
wurzel env examples.pipeline.pipelinedemo:pipeline --gen-env > .env.sample

# Fail fast when something is missing
wurzel env examples.pipeline.pipelinedemo:pipeline --check
# Allow dynamically added settings (equivalent to setting ALLOW_EXTRA_SETTINGS)
wurzel env examples.pipeline.pipelinedemo:pipeline --check --allow-extra-fields
```

### Generating Pipelines

The `wurzel generate` command creates backend-specific pipeline configurations from chained pipelines.

**Arguments:**
- `pipeline` - Module path to a chained pipeline (multiple steps combined with `>>` operator)

**Options:**
- `-b, --backend` - Backend to use (default: DvcBackend). Case-insensitive.
- `--list-backends` - List all available backends and exit

```bash
# List all available backends
wurzel generate --list-backends

# Generate from a chained pipeline
wurzel generate examples.pipeline.pipelinedemo.pipeline

# Generate with explicit backend (case-insensitive)
wurzel generate myproject.pipelines.MyPipeline --backend DvcBackend
wurzel generate myproject.pipelines.MyPipeline -b dvcbackend

# Generate Argo Workflows pipeline (requires wurzel[argo])
wurzel generate myproject.pipelines.MyPipeline --backend ArgoBackend
wurzel generate myproject.pipelines.MyPipeline -b argobackend
```

**Creating a Chained Pipeline:**

A chained pipeline is created by combining multiple steps with the `>>` operator:

```python
# In myproject/pipelines.py
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.steps.splitter import SimpleSplitterStep
from wurzel.utils import WZ

# Wrap steps with WZ
source = WZ(ManualMarkdownStep)
splitter = WZ(SimpleSplitterStep)

# Chain steps together
source >> splitter

# Export the final step as the pipeline
pipeline = splitter
```

Then generate the pipeline configuration:
```bash
wurzel generate myproject.pipelines.pipeline -b DvcBackend
```

## Step Auto-Discovery

The CLI supports intelligent auto-completion for step names using TAB completion:

```bash
wurzel run <TAB>                    # Shows all available steps
wurzel run wurzel.steps.<TAB>       # Shows wurzel built-in steps
wurzel run mysteps.<TAB>            # Shows your custom steps
```

The auto-completion discovers:

1. **Built-in Wurzel steps** - Available in the `wurzel.steps.*` namespace
2. **User-defined steps** - TypedStep classes in your current project
