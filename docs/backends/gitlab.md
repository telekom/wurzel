# GitLab CI/CD Backend

The GitLab CI/CD Backend transforms your Wurzel pipeline into `.gitlab-ci.yml` configuration files, enabling native GitLab CI/CD orchestration with parallel execution, caching, and artifact management.

## Overview

GitLab CI/CD is a powerful continuous integration and delivery platform built into GitLab. The GitLab Backend generates `.gitlab-ci.yml` files that define your pipeline as GitLab CI jobs with dependencies, allowing for parallel execution and sophisticated workflow control.

!!! important "Generate-Time vs Runtime Configuration"
    The GitLab backend uses a **two-phase configuration model**:

    - **Generate-Time (YAML)**: A `values.yaml` file configures the **pipeline structure** — container images, variables, cache settings, job configurations, and stages. This is used when running `wurzel generate`.
    - **Runtime (Environment Variables)**: **Step settings** (e.g., `MANUALMARKDOWNSTEP__FOLDER_PATH`) are read from environment variables when GitLab CI executes the pipeline. These can be set via `variables` in your `values.yaml` or in GitLab CI/CD settings.

    This separation allows you to generate pipeline definitions once and run them in different environments by changing only the runtime environment variables.

## Key Features

- **Native GitLab Integration**: Run pipelines directly on GitLab Runners
- **Parallel Execution**: Automatic parallelization using `needs` keyword
- **Artifact Management**: Pass data between jobs with configurable expiration
- **Flexible Caching**: Speed up builds with GitLab's caching mechanisms
- **Advanced Job Control**: Tags, timeouts, retries, and conditional execution with rules
- **Multi-Stage Pipelines**: Organize jobs into logical stages

## Usage

### CLI Usage

Generate a GitLab CI/CD pipeline configuration:

```bash
# Install Wurzel
pip install wurzel

# Generate .gitlab-ci.yml using GitLab backend
wurzel generate --backend GitlabBackend \
    --output .gitlab-ci.yml \
    examples.pipeline.pipelinedemo:pipeline

# Generate using a values file (recommended)
wurzel generate --backend GitlabBackend \
    --values values.yaml \
    --pipeline_name pipelinedemo \
    --output .gitlab-ci.yml \
    examples.pipeline.pipelinedemo:pipeline
```

### Values File Configuration (Generate-Time)

The `values.yaml` file configures the pipeline structure at generate-time. Here's a complete example:

```yaml
gitlab:
  pipelinedemo:
    # Data directory for step outputs
    dataDir: ./data
    encapsulateEnv: true

    # Container image configuration
    image:
      name: ghcr.io/telekom/wurzel:latest
      pull_policy: if-not-present  # optional: always, if-not-present, never

    # Global variables (runtime environment)
    variables:
      MANUALMARKDOWNSTEP__FOLDER_PATH: "examples/pipeline/demo-data"
      SIMPLESPLITTERSTEP__BATCH_SIZE: "100"
      PIPELINE_ENV: "production"

    # Pipeline stages
    stages:
      - extract
      - transform
      - load

    # Cache configuration
    cache:
      paths:
        - .cache/pip
        - .venv
      key: "${CI_COMMIT_REF_SLUG}"
      policy: pull-push  # pull, push, or pull-push

    # Artifact configuration (default for all jobs)
    artifacts:
      paths:
        - data/
      expire_in: 1 week
      when: on_success  # on_success, on_failure, or always

    # Default job configuration
    defaultJob:
      stage: process
      tags:
        - docker
        - linux
      timeout: 1h
      retry: 2
      allow_failure: false
      rules:
        - if: $CI_COMMIT_BRANCH == "main"
      before_script:
        - pip install -q wurzel
        - echo "Starting job..."
      after_script:
        - echo "Job completed!"
```

### Configuration Reference

#### Pipeline-Level Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dataDir` | path | `./data` | Directory for step output artifacts |
| `encapsulateEnv` | bool | `true` | Whether to encapsulate environment in CLI calls |

#### Image Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | `ghcr.io/telekom/wurzel:latest` | Container image name |
| `pull_policy` | string | `null` | Image pull policy: `always`, `if-not-present`, or `never` |

#### Variables Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `variables` | map[string]string | `{}` | Global variables available to all jobs (runtime env vars) |

#### Stages Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `stages` | list[string] | `["process"]` | List of pipeline stages |

#### Cache Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `paths` | list[string] | `[]` | Paths to cache |
| `key` | string | `${CI_COMMIT_REF_SLUG}` | Cache key (supports GitLab CI variables) |
| `policy` | string | `pull-push` | Cache policy: `pull`, `push`, or `pull-push` |

#### Artifacts Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `paths` | list[string] | `["data/"]` | Paths to store as artifacts |
| `expire_in` | string | `1 week` | Artifact expiration (e.g., `30 mins`, `2 hrs`, `1 day`, `1 week`) |
| `when` | string | `on_success` | When to upload: `on_success`, `on_failure`, or `always` |

#### Default Job Configuration

These settings apply to all generated jobs:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `stage` | string | `process` | Stage name for all jobs |
| `tags` | list[string] | `[]` | Runner tags for job execution |
| `timeout` | string | `null` | Job timeout (e.g., `30m`, `1h`, `2h 30m`) |
| `retry` | int or dict | `0` | Number of retry attempts (or retry config object) |
| `allow_failure` | bool | `false` | Whether job failure should fail the pipeline |
| `rules` | list[dict] | `[]` | Conditional execution rules |
| `before_script` | list[string] | `[]` | Commands to run before job script |
| `after_script` | list[string] | `[]` | Commands to run after job script |

### Runtime Environment Variables

Step settings are configured via environment variables at **runtime** (when GitLab CI executes the pipeline). These can be set in three ways:

1. **In `variables` section**: Directly in the values file
2. **GitLab CI/CD Variables**: In project or group settings (Settings → CI/CD → Variables)
3. **GitLab CI/CD Files**: Using `.env` files or variable files

```yaml
# In values.yaml (generate-time)
gitlab:
  pipelinedemo:
    variables:
      # Runtime step settings
      MANUALMARKDOWNSTEP__FOLDER_PATH: "examples/pipeline/demo-data"
      SIMPLESPLITTERSTEP__BATCH_SIZE: "100"
      SIMPLESPLITTERSTEP__NUM_THREADS: "4"
```

!!! tip "Inspecting Required Environment Variables"
    Use `wurzel inspect` to see all environment variables required by your pipeline steps:
    ```bash
    wurzel inspect examples.pipeline.pipelinedemo:pipeline --gen-env
    ```

### Programmatic Usage

Use the GitLab backend directly in Python:

```python
from pathlib import Path
from wurzel.backend.backend_gitlab import GitlabBackend, GitlabConfig, GitlabImageConfig

# Create backend with configuration
backend = GitlabBackend(config=GitlabConfig(
    dataDir=Path("./data"),
    encapsulateEnv=True,
    image=GitlabImageConfig(name="python:3.12"),
    variables={"PIPELINE_ENV": "production"},
    stages=["extract", "transform", "load"],
))

# Generate .gitlab-ci.yml
yaml_output = backend.generate_artifact(my_step)

# Write to file
with open(".gitlab-ci.yml", "w") as f:
    f.write(yaml_output)
```

Alternatively, load configuration from a values file:

```python
from pathlib import Path
from wurzel.backend.backend_gitlab import GitlabBackend

# Load from values file
backend = GitlabBackend.from_values(
    files=[Path("values.yaml")],
    workflow_name="pipelinedemo"
)

# Generate .gitlab-ci.yml
yaml_output = backend.generate_artifact(my_step)
```

## Generated Pipeline Structure

The GitLab backend generates a `.gitlab-ci.yml` file with the following structure:

```yaml
image: python:3.12

variables:
  PIPELINE_ENV: production

stages:
  - extract
  - transform
  - load

ExtractStep:
  stage: process
  script:
    - wurzel run module:ExtractStep -o ./data/ExtractStep
  artifacts:
    paths:
      - data/ExtractStep
    expire_in: 1 week
    when: on_success

TransformStep:
  stage: process
  script:
    - wurzel run module:TransformStep -o ./data/TransformStep -i data/ExtractStep
  artifacts:
    paths:
      - data/TransformStep
    expire_in: 1 week
    when: on_success
  needs:
    - ExtractStep

LoadStep:
  stage: process
  script:
    - wurzel run module:LoadStep -o ./data/LoadStep -i data/TransformStep
  artifacts:
    paths:
      - data/LoadStep
    expire_in: 1 week
    when: on_success
  needs:
    - TransformStep
```

### Job Dependencies

The backend automatically generates job dependencies using the `needs` keyword based on your step graph:

- **Parallel Execution**: Jobs without dependencies run in parallel
- **Sequential Execution**: Jobs with dependencies wait for their predecessors
- **Efficient Scheduling**: GitLab CI optimally schedules jobs based on the dependency graph

## Advanced Features

### Conditional Execution with Rules

Control when jobs run using GitLab CI/CD rules:

```yaml
gitlab:
  pipelinedemo:
    defaultJob:
      rules:
        # Run only on main branch
        - if: $CI_COMMIT_BRANCH == "main"
        # Or on merge requests
        - if: $CI_PIPELINE_SOURCE == "merge_request_event"
        # Or when manually triggered
        - if: $CI_PIPELINE_SOURCE == "web"
```

### Retry Configuration

Configure automatic retries for transient failures:

```yaml
gitlab:
  pipelinedemo:
    defaultJob:
      retry:
        max: 2
        when:
          - runner_system_failure
          - stuck_or_timeout_failure
```

Or use a simple integer for all failure types:

```yaml
gitlab:
  pipelinedemo:
    defaultJob:
      retry: 2
```

### Runner Tags

Target specific GitLab Runners using tags:

```yaml
gitlab:
  pipelinedemo:
    defaultJob:
      tags:
        - docker
        - linux
        - large-memory
```

### Cache Configuration

Speed up builds by caching dependencies:

```yaml
gitlab:
  pipelinedemo:
    cache:
      paths:
        - .cache/pip
        - .venv
        - node_modules
      key: "${CI_COMMIT_REF_SLUG}"
      policy: pull-push
```

## Deployment

### Commit to Repository

Add the generated `.gitlab-ci.yml` to your repository:

```bash
# Generate the pipeline
wurzel generate --backend GitlabBackend \
    --values values.yaml \
    --output .gitlab-ci.yml \
    examples.pipeline.pipelinedemo:pipeline

# Commit and push
git add .gitlab-ci.yml
git commit -m "Add Wurzel pipeline"
git push
```

GitLab CI will automatically detect the `.gitlab-ci.yml` file and start running your pipeline.

### Running Locally

Test your pipeline locally using GitLab Runner:

```bash
# Install GitLab Runner
# See: https://docs.gitlab.com/runner/install/

# Run a specific job
gitlab-runner exec docker ExtractStep
```

## Best Practices

### 1. Use Values Files for Configuration

Always use values files for configuration management:

```bash
# Recommended
wurzel generate --backend GitlabBackend --values values.yaml ...

# Avoid hardcoding configuration in code
```

### 2. Set Appropriate Artifact Expiration

Balance storage costs with retention needs:

```yaml
gitlab:
  pipelinedemo:
    artifacts:
      expire_in: 1 week  # or 30 mins, 2 hrs, 1 day, etc.
```

### 3. Use Cache for Dependencies

Cache package installations to speed up builds:

```yaml
gitlab:
  pipelinedemo:
    cache:
      paths:
        - .cache/pip
      key: "${CI_COMMIT_REF_SLUG}"
    defaultJob:
      before_script:
        - pip install --cache-dir=.cache/pip wurzel
```

### 4. Tag Runners Appropriately

Use specific runners for resource-intensive jobs:

```yaml
gitlab:
  pipelinedemo:
    defaultJob:
      tags:
        - docker
        - high-memory  # For memory-intensive steps
```

### 5. Set Timeouts to Prevent Hanging Jobs

Prevent jobs from running indefinitely:

```yaml
gitlab:
  pipelinedemo:
    defaultJob:
      timeout: 1h
```

### 6. Use Rules for Branch-Specific Execution

Control pipeline execution based on branches:

```yaml
gitlab:
  pipelinedemo:
    defaultJob:
      rules:
        - if: $CI_COMMIT_BRANCH == "main"
        - if: $CI_COMMIT_BRANCH =~ /^release-/
```

## Troubleshooting

### Pipeline Not Starting

**Issue**: GitLab CI doesn't detect your pipeline.

**Solution**: Ensure `.gitlab-ci.yml` is in the repository root and properly formatted:

```bash
# Validate YAML syntax
yamllint .gitlab-ci.yml

# Check GitLab CI lint
# Go to: Repository → CI/CD → Pipelines → CI Lint
```

### Jobs Failing with "wurzel: command not found"

**Issue**: Wurzel is not installed in the container.

**Solution**: Add installation to `before_script`:

```yaml
gitlab:
  pipelinedemo:
    defaultJob:
      before_script:
        - pip install wurzel
```

### Artifacts Not Available Between Jobs

**Issue**: Downstream jobs can't find artifacts from upstream jobs.

**Solution**: Ensure artifacts are configured and jobs use `needs`:

```yaml
# Artifacts are automatically configured by the backend
# Verify in the generated .gitlab-ci.yml that:
# 1. Jobs have artifacts.paths set
# 2. Dependent jobs have needs set correctly
```

### Jobs Running Sequentially Instead of Parallel

**Issue**: All jobs run one after another.

**Solution**: The backend automatically uses `needs` for dependencies. Jobs without dependencies run in parallel. Check your step graph:

```python
# Correct: Parallel execution
step1 = Step1()
step2 = Step2()
step3 = Step3()
# step1, step2, step3 run in parallel

# Sequential: step1 -> step2 -> step3
step1 >> step2 >> step3
```

## Comparison with Other Backends

| Feature | GitLab Backend | DVC Backend | Argo Backend |
|---------|---------------|-------------|--------------|
| **Execution** | GitLab Runners | Local or remote | Kubernetes cluster |
| **Parallelization** | Native with `needs` | Limited | Native with DAGs |
| **Scheduling** | GitLab CI schedules | Manual with cron | Kubernetes CronWorkflow |
| **Artifact Storage** | GitLab artifacts | DVC remote | S3-compatible |
| **Scalability** | Runner-dependent | Single machine | Kubernetes-native |
| **Caching** | GitLab cache | DVC cache | Kubernetes volumes |
| **UI** | GitLab CI/CD | DVC Studio | Argo UI |
| **Best For** | GitLab users, CI/CD integration | Local development, ML experiments | Cloud-native, large-scale |

## Next Steps

- **[Backend Architecture](index.md)**: Learn about the backend abstraction layer
- **[DVC Backend](dvc.md)**: Alternative for local ML workflows
- **[Argo Backend](argoworkflows.md)**: Alternative for Kubernetes deployments
- **[GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)**: Official GitLab CI/CD docs

## Example: Complete ETL Pipeline

Here's a complete example of an ETL pipeline with the GitLab backend:

```python
# pipeline.py
from wurzel.step import TypedStep, NoSettings
from wurzel.datacontract.common import MarkdownDataContract

class ExtractStep(TypedStep[NoSettings, None, MarkdownDataContract]):
    """Extract data from source."""
    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(content="extracted data")

class TransformStep(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
    """Transform the data."""
    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return MarkdownDataContract(content=f"transformed: {inpt.content}")

class LoadStep(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
    """Load data to destination."""
    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return MarkdownDataContract(content=f"loaded: {inpt.content}")

# Build pipeline
extract = ExtractStep()
transform = TransformStep()
load = LoadStep()

extract >> transform >> load

# Export for generation
pipeline = load
```

```yaml
# values.yaml
gitlab:
  etl-pipeline:
    dataDir: ./pipeline-data
    image:
      name: python:3.12-slim
    variables:
      PIPELINE_ENV: production
      LOG_LEVEL: INFO
    stages:
      - extract
      - transform
      - load
    cache:
      paths:
        - .cache/pip
      key: "${CI_COMMIT_REF_SLUG}"
    defaultJob:
      tags:
        - docker
      timeout: 30m
      retry: 2
      before_script:
        - pip install --cache-dir=.cache/pip wurzel
      rules:
        - if: $CI_COMMIT_BRANCH == "main"
```

```bash
# Generate .gitlab-ci.yml
wurzel generate --backend GitlabBackend \
    --values values.yaml \
    --pipeline_name etl-pipeline \
    --output .gitlab-ci.yml \
    pipeline:pipeline

# Commit and push
git add .gitlab-ci.yml values.yaml pipeline.py
git commit -m "Add ETL pipeline"
git push

# Pipeline runs automatically on GitLab
```
