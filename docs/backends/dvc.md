# DVC Backend

The DVC Backend transforms your Wurzel pipeline into Data Version Control (DVC) configuration files, enabling reproducible machine learning workflows with built-in data versioning and experiment tracking.

## Overview

DVC (Data Version Control) is a powerful tool for ML experiment management that works seamlessly with Git. The DVC Backend generates `dvc.yaml` files that define your pipeline stages, dependencies, and outputs in a format that DVC can execute and track.

!!! important "Generate-Time vs Runtime Configuration"
    The DVC backend uses a **two-phase configuration model**:

    - **Generate-Time (YAML or Environment)**: A `values.yaml` file or environment variables configure the **pipeline structure** — data directories and environment encapsulation settings. This is used when running `wurzel generate`.
    - **Runtime (Environment Variables)**: **Step settings** (e.g., `MANUALMARKDOWNSTEP__FOLDER_PATH`) are read from environment variables when `dvc repro` executes the pipeline locally.

    This separation allows you to generate pipeline definitions once and run them in different environments by changing only the runtime environment variables.

## Key Features

- **Data Versioning**: Automatically track changes to datasets and model artifacts
- **Reproducible Pipelines**: Generate deterministic pipeline definitions
- **Experiment Tracking**: Compare different pipeline runs and their results
- **Git Integration**: Version control your pipeline configurations alongside your code
- **Caching**: Intelligent caching of intermediate results to speed up development

## Usage

### CLI Usage

Generate a DVC pipeline configuration:

```bash
# Install Wurzel
pip install wurzel

# Generate dvc.yaml (default backend)
wurzel generate examples.pipeline.pipelinedemo:pipeline

# Explicitly specify DVC backend
wurzel generate --backend DvcBackend --output dvc.yaml examples.pipeline.pipelinedemo:pipeline

# Generate using a values file (recommended)
wurzel generate --backend DvcBackend \
    --values values.yaml \
    --pipeline_name pipelinedemo \
    --output dvc.yaml \
    examples.pipeline.pipelinedemo:pipeline
```

### Values File Configuration (Generate-Time)

The `values.yaml` file configures the pipeline structure at generate-time:

```yaml
dvc:
  pipelinedemo:
    dataDir: "./data"        # Directory for step outputs
    encapsulateEnv: true     # Whether to encapsulate environment in CLI calls
```

### Environment Configuration (Generate-Time Alternative)

Alternatively, configure the DVC backend using environment variables at generate-time:

```bash
export DVCBACKEND__DATA_DIR=./data
export DVCBACKEND__ENCAPSULATE_ENV=true
```

### Configuration Reference

| Field | Environment Variable | Default | Description |
|-------|---------------------|---------|-------------|
| `dataDir` | `DVCBACKEND__DATA_DIR` | `./data` | Directory for step output artifacts |
| `encapsulateEnv` | `DVCBACKEND__ENCAPSULATE_ENV` | `true` | Whether to encapsulate environment in CLI calls |

### Runtime Environment Variables

Step settings are configured via environment variables at **runtime** (when `dvc repro` executes). Set these before running your pipeline:

```bash
# Step-specific settings (runtime)
export MANUALMARKDOWNSTEP__FOLDER_PATH="examples/pipeline/demo-data"
export SIMPLESPLITTERSTEP__BATCH_SIZE="100"
export SIMPLESPLITTERSTEP__NUM_THREADS="4"

# Run the pipeline
dvc repro
```

!!! tip "Inspecting Required Environment Variables"
    Use `wurzel inspect` to see all environment variables required by your pipeline steps:
    ```bash
    wurzel inspect examples.pipeline.pipelinedemo:pipeline --gen-env
    ```

### Programmatic Usage

Use the DVC backend directly in Python:

```python
from pathlib import Path
from wurzel.backend.backend_dvc import DvcBackend
from wurzel.steps.embedding import EmbeddingStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.steps.qdrant.step import QdrantConnectorStep
from wurzel.utils import WZ

# Define your pipeline
source = WZ(ManualMarkdownStep)
embedding = WZ(EmbeddingStep)
step = WZ(QdrantConnectorStep)

source >> embedding >> step
pipeline = step

# Option 1: Generate DVC configuration from values file
backend = DvcBackend.from_values(
    files=[Path("values.yaml")],
    workflow_name="pipelinedemo"
)
dvc_yaml = backend.generate_artifact(pipeline)
print(dvc_yaml)

# Option 2: Generate with default settings
dvc_yaml = DvcBackend().generate_artifact(pipeline)
print(dvc_yaml)
```

## Running DVC Pipelines

Once you've generated your `dvc.yaml` file, you can execute the pipeline using DVC:

```bash
# Run the entire pipeline
dvc repro

# Run specific stages
dvc repro <stage_name>

# Show pipeline status
dvc status

# Compare experiments
dvc plots show
```

## Benefits for ML Workflows

### Data Lineage

Track the complete history of your data transformations, making it easy to understand how your final model was created.

### Experiment Reproducibility

Every pipeline run is completely reproducible, with DVC tracking all inputs, parameters, and outputs.

### Collaborative Development

Share pipeline definitions through Git while DVC handles the heavy lifting of data and model versioning.

### Performance Optimization

DVC's intelligent caching means you only recompute what's changed, dramatically speeding up iterative development.

## Learn More

- [DVC Documentation](https://dvc.org/doc)
- [Back to Backend Overview](./index.md)
