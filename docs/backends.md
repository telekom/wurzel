# Wurzel: Using DVC and Argo Workflows Backends

Wurzel supports multiple backends to generate pipeline configuration for different execution environments.

This document explains how to use the DvcBackend and ArgoBackend through the Wurzel CLI and highlights available and upcoming backends.

---

Backend Overview:

- DvcBackend: Generates `dvc.yaml`, used with `dvc repro` or versioned pipelines.
- ArgoBackend: Generates Argo Workflows `CronWorkflow` YAML for Kubernetes-native scheduled pipelines.

Note: The CLI uses `DvcBackend` by default if no backend is explicitly specified.

---

## CLI Usage

To use Wurzel's CLI for generating pipeline definitions, follow these instructions:

1. Install the necessary dependencies:

    pip install wurzel[argo]

2. Run the CLI:

    wurzel generate examples.pipeline.pipelinedemo:pipeline

This generates a `dvc.yaml` by default using the `DvcBackend`.

To specify a different backend or output file:

    wurzel generate --backend DvcBackend --output dvc.yaml examples.pipeline.pipelinedemo:pipeline

    wurzel generate --backend ArgoBackend --output cronworkflow.yaml examples.pipeline.pipelinedemo:pipeline

Replace `pipeline:pipeline` with your actual module path and step name.

---

## Environment Configuration

You can configure each backend via environment variables.

Example for DVC:

    export DVCBACKEND__DATA_DIR=./data
    export DVCBACKEND__ENCAPSULATE_ENV=true

Example for Argo:

    export ARGOWORKFLOWBACKEND__IMAGE=ghcr.io/telekom/wurzel
    export ARGOWORKFLOWBACKEND__SCHEDULE="0 4 * * *"
    export ARGOWORKFLOWBACKEND__DATA_DIR=/usr/app
    export ARGOWORKFLOWBACKEND__ENCAPSULATE_ENV=true
    export ARGOWORKFLOWBACKEND__S3_ARTIFACT_TEMPLATE__BUCKET=wurzel-bucket
    export ARGOWORKFLOWBACKEND__S3_ARTIFACT_TEMPLATE__ENDPOINT=s3.amazonaws.com
    export ARGOWORKFLOWBACKEND__SERVICE_ACCOUNT_NAME=wurzel-service-account
    export ARGOWORKFLOWBACKEND__SECRET_NAME=wurzel-secret
    export ARGOWORKFLOWBACKEND__CONFIG_MAP=wurzel-config
    export ARGOWORKFLOWBACKEND__PIPELINE_NAME=my-wurzel-pipeline

---

## Programmatic Usage

You can also use the backends directly in Python:

    from wurzel.backend.dvc import DvcBackend
    from wurzel.backend.argo import ArgoBackend
    from wurzel.steps.embedding import EmbeddingStep
    from wurzel.steps.manual_markdown import ManualMarkdownStep
    from wurzel.steps.qdrant.step import QdrantConnectorStep
    from wurzel.utils import WZ

    source = WZ(ManualMarkdownStep)
    embedding = WZ(EmbeddingStep)
    step = WZ(QdrantConnectorStep)


    source >> embedding >> step
    pipeline = step

    dvc_yaml = DvcBackend().generate_yaml(pipeline)
    argo_yaml = ArgoBackend().generate_yaml(pipeline)

---

## Future Backends

Wurzel is designed to support additional backends. Potential future targets include:

- GitLab CI/CD: For generating `.gitlab-ci.yml` pipelines
- GitHub Actions: To produce `workflow.yml` for GitHub-native automation
- Apache Airflow: For DAG-based orchestration and scheduling
- LocalBackend: Execute steps locally without an external orchestrator
- Kubernetes CronJobs: A planned enhancement to `DvcBackend` to support rendering Kubernetes-native `CronJob` manifests for scheduled execution of DVC pipelines

These additions will further expand the flexibility of Wurzel across various deployment and orchestration environments.

---

## Documentation

For more details, see:

- DVC: https://dvc.org/doc
- Argo Workflows: https://argoproj.github.io/argo-workflows/
- Automatic created Wurzel project documentation: https://deepwiki.com/telekom/wurzel/
