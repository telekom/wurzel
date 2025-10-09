# Argo Workflows Backend

The Argo Workflows Backend transforms your Wurzel pipeline into Kubernetes-native CronWorkflow YAML configurations, enabling cloud-native, scalable pipeline orchestration with advanced scheduling capabilities.

## Overview

Argo Workflows is a powerful, Kubernetes-native workflow engine that excels at container orchestration and parallel execution. The Argo Backend generates `CronWorkflow` YAML files that leverage Kubernetes' native scheduling and resource management capabilities.

## Key Features

- **Cloud-Native Orchestration**: Run pipelines natively on Kubernetes clusters
- **Horizontal Scaling**: Automatically scale pipeline steps based on resource requirements
- **Advanced Scheduling**: Cron-based scheduling with fine-grained control
- **Resource Management**: Leverage Kubernetes resource limits and requests
- **Artifact Management**: Integrated S3-compatible artifact storage
- **Service Integration**: Seamless integration with Kubernetes services and secrets

## Usage

### Installation

Install Wurzel with Argo support:

```bash
pip install wurzel[argo]
```

### CLI Usage

Generate an Argo Workflows CronWorkflow configuration:

```bash
# Generate cronworkflow.yaml using Argo backend
wurzel generate --backend ArgoBackend --output cronworkflow.yaml examples.pipeline.pipelinedemo:pipeline
```

### Environment Configuration

Configure the Argo backend using environment variables:

```bash
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
```

Available configuration options:

- `IMAGE`: Container image to use for pipeline execution
- `SCHEDULE`: Cron schedule for automatic pipeline execution
- `DATA_DIR`: Directory path within the container for data files
- `ENCAPSULATE_ENV`: Whether to encapsulate environment variables
- `S3_ARTIFACT_TEMPLATE__BUCKET`: S3 bucket for artifact storage
- `S3_ARTIFACT_TEMPLATE__ENDPOINT`: S3 endpoint URL
- `SERVICE_ACCOUNT_NAME`: Kubernetes service account for pipeline execution
- `SECRET_NAME`: Kubernetes secret containing credentials
- `CONFIG_MAP`: Kubernetes ConfigMap for configuration
- `PIPELINE_NAME`: Name for the generated CronWorkflow

### Programmatic Usage

Use the Argo backend directly in Python:

```python
from wurzel.executors.backend.backend_argo import ArgoBackend
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

# Generate Argo Workflows configuration
argo_yaml = ArgoBackend().generate_yaml(pipeline)
print(argo_yaml)
```

## Deploying Argo Workflows

Once you've generated your CronWorkflow YAML, deploy it to your Kubernetes cluster:

```bash
# Apply the CronWorkflow to your cluster
kubectl apply -f cronworkflow.yaml

# Monitor workflow executions
argo list

# Check workflow logs
argo logs <workflow-name>

# Get workflow status
argo get <workflow-name>
```

## Benefits for Cloud-Native Pipelines

### Kubernetes-Native Execution

Leverage the full power of Kubernetes for container orchestration, resource management, and fault tolerance.

### Scalable Processing

Automatically scale pipeline steps based on workload requirements, with support for parallel execution across multiple nodes.

### Enterprise Security

Integrate with Kubernetes RBAC, service accounts, and network policies for enterprise-grade security.

### Cost Optimization

Take advantage of Kubernetes features like node auto-scaling and spot instances to optimize infrastructure costs.

### Observability

Built-in integration with Kubernetes monitoring tools and Argo's web UI for comprehensive pipeline observability.

## Prerequisites

- Kubernetes cluster with Argo Workflows installed
- kubectl configured to access your cluster
- Appropriate RBAC permissions for workflow execution
- S3-compatible storage for artifacts (optional but recommended)

## Learn More

- [Argo Workflows Documentation](https://argoproj.github.io/argo-workflows/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Back to Backend Overview](./index.md)
