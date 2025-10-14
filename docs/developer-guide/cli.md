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
wurzel generate wurzel.steps.manual_markdown.ManualMarkdownStep
```

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

### Generating Pipelines

```bash
# Generate DVC pipeline (default)
wurzel generate wurzel.steps.manual_markdown.ManualMarkdownStep

# Generate Argo pipeline
wurzel generate wurzel.steps.manual_markdown.ManualMarkdownStep --backend ArgoBackend
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

### Performance Optimizations

The CLI auto-completion is optimized for speed:

- ✅ **Fast scanning** - Only scans relevant directories
- ✅ **Smart exclusions** - Skips `.venv`, `tests`, `docs`, `__pycache__`, etc.
- ✅ **AST parsing** - Analyzes code without importing modules
- ✅ **Depth limiting** - Prevents deep directory traversal
