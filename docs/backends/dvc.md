# DVC Backend

The DVC Backend transforms your Wurzel pipeline into Data Version Control (DVC) configuration files, enabling reproducible machine learning workflows with built-in data versioning and experiment tracking.

## Overview

DVC (Data Version Control) is a powerful tool for ML experiment management that works seamlessly with Git. The DVC Backend generates `dvc.yaml` files that define your pipeline stages, dependencies, and outputs in a format that DVC can execute and track.

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
```

### Environment Configuration

Configure the DVC backend using environment variables:

```bash
export DVCBACKEND__DATA_DIR=./data
export DVCBACKEND__ENCAPSULATE_ENV=true
```

Available configuration options:

- `DVCBACKEND__DATA_DIR`: Directory for data files (default: `./data`)
- `DVCBACKEND__ENCAPSULATE_ENV`: Whether to encapsulate environment variables (default: `false`)

### Programmatic Usage

Use the DVC backend directly in Python:

```python
from wurzel.backend.dvc import DvcBackend
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

# Generate DVC configuration
dvc_yaml = DvcBackend().generate_yaml(pipeline)
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
