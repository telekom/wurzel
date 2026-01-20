# Argo Workflows Backend

The Argo Workflows Backend transforms your Wurzel pipeline into Kubernetes-native Workflow or CronWorkflow YAML configurations, enabling cloud-native, scalable pipeline orchestration with optional scheduling capabilities.

## Overview

Argo Workflows is a powerful, Kubernetes-native workflow engine that excels at container orchestration and parallel execution. The Argo Backend generates either:

- **`Workflow`**: For one-time or manually triggered pipeline executions (when `schedule: null`)
- **`CronWorkflow`**: For scheduled, recurring pipeline executions (when a cron schedule is provided)

Both workflow types leverage Kubernetes' native scheduling and resource management capabilities.

!!! important "Generate-Time vs Runtime Configuration"
    The Argo backend uses a **two-phase configuration model**:

    - **Generate-Time (YAML)**: A `values.yaml` file configures the **workflow structure** — container images, namespaces, schedules, security contexts, resource limits, and artifact storage. This is required when running `wurzel generate`.
    - **Runtime (Environment Variables)**: **Step settings** (e.g., `MANUALMARKDOWNSTEP__FOLDER_PATH`) are read from environment variables when the workflow executes in Kubernetes. These can be set via `container.env`, Secrets, or ConfigMaps in your `values.yaml`.

    This separation allows you to generate workflow manifests once and deploy them to different environments by changing only the runtime environment variables.

## Key Features

- **Cloud-Native Orchestration**: Run pipelines natively on Kubernetes clusters
- **Flexible Execution**: Support for both one-time Workflows and scheduled CronWorkflows
- **Horizontal Scaling**: Automatically scale pipeline steps based on resource requirements
- **Advanced Scheduling**: Optional cron-based scheduling with fine-grained control
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

Generate an Argo Workflows configuration using a `values.yaml` file:

```bash
# Generate a CronWorkflow with scheduled execution
wurzel generate --backend ArgoBackend \
    --values values.yaml \
    --pipeline_name pipelinedemo \
    --output cronworkflow.yaml \
    examples.pipeline.pipelinedemo:pipeline

# Or generate a one-time Workflow (set schedule: null in values.yaml)
wurzel generate --backend ArgoBackend \
    --values values-no-schedule.yaml \
    --pipeline_name pipelinedemo \
    --output workflow.yaml \
    examples.pipeline.pipelinedemo:pipeline
```

!!! note
    The `--values` flag is **required** for the Argo backend. It specifies the YAML configuration file that defines the workflow structure.

### Values File Configuration (Generate-Time)

The `values.yaml` file configures the workflow structure at generate-time. Here's a complete example:

```yaml
workflows:
  pipelinedemo:
    # Workflow metadata
    name: wurzel-pipeline
    namespace: argo-workflows
    schedule: "0 4 * * *"  # Cron schedule for CronWorkflow, or null for one-time Workflow
    entrypoint: wurzel-pipeline
    serviceAccountName: wurzel-service-account
    dataDir: /data

    # Workflow-level annotations
    annotations:
      sidecar.istio.io/inject: "false"

    # Pod-level security context (applied to all pods)
    podSecurityContext:
      runAsNonRoot: true
      runAsUser: 1000
      runAsGroup: 1000
      fsGroup: 2000
      fsGroupChangePolicy: Always  # or "OnRootMismatch"
      supplementalGroups:
        - 1000
      seccompProfileType: RuntimeDefault

    # Optional: Custom podSpecPatch for advanced use cases
    # podSpecPatch: |
    #   initContainers:
    #     - name: custom-init
    #       securityContext:
    #         runAsNonRoot: true

    # Container configuration
    container:
      image: ghcr.io/telekom/wurzel

      # Container-level security context
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        dropCapabilities:
          - ALL
        seccompProfileType: RuntimeDefault

      # Resource requests and limits
      resources:
        cpu_request: "100m"
        cpu_limit: "500m"
        memory_request: "128Mi"
        memory_limit: "512Mi"

      # Runtime environment variables (step settings)
      env:
        # Step-specific settings
        MANUALMARKDOWNSTEP__FOLDER_PATH: "examples/pipeline/demo-data"
        SIMPLESPLITTERSTEP__BATCH_SIZE: "100"

        # Middleware configuration (optional)
        # Enable Prometheus middleware for metrics collection
        MIDDLEWARES: "prometheus"
        PROMETHEUS__PROMETHEUS_GATEWAY: "prometheus-pushgateway.monitoring.svc.cluster.local:9091"
        PROMETHEUS__PROMETHEUS_JOB: "wurzel-pipeline"  # optional
        PROMETHEUS__PROMETHEUS_DISABLE_CREATED_METRIC: "true"  # optional

      # Environment from Kubernetes Secrets/ConfigMaps
      envFrom:
        - kind: secret
          name: wurzel-env-secret
          prefix: ""
          optional: true
        - kind: configMap
          name: wurzel-env-config
          prefix: APP_
          optional: true

      # Reference existing secrets as env vars
      secretRef:
        - "wurzel-secrets"

      # Reference existing configmaps as env vars
      configMapRef:
        - "wurzel-config"

      # Mount secrets as files
      mountSecrets:
        - from: "tls-secret"
          to: "/etc/ssl"
          mappings:
            - key: "tls.crt"
              value: "cert.pem"
            - key: "tls.key"
              value: "key.pem"

      # Tokenizer cache volume (for HuggingFace models)
      tokenizerCache:
        enabled: true
        claimName: tokenizer-cache-pvc  # Used when createPvc: false
        mountPath: /cache/huggingface
        readOnly: true
        # To auto-create a workflow-scoped PVC:
        # createPvc: true
        # storageSize: 10Gi
        # storageClassName: standard
        # accessModes: ["ReadWriteOnce"]

    # S3 artifact storage configuration
    artifacts:
      bucket: wurzel-bucket
      endpoint: s3.amazonaws.com
      defaultMode: 509  # File permissions (decimal), e.g., 509 = 0o775
```

### Workflow vs CronWorkflow

The Argo backend generates different workflow types based on the `schedule` configuration:

#### Normal Workflow (One-Time Execution)

Set `schedule: null` (or omit it) to create a **Workflow** for manual or one-time execution:

```yaml
workflows:
  my-workflow:
    name: my-pipeline
    schedule: null  # Creates a Workflow, not a CronWorkflow
```

**Use cases:**
- Manual pipeline execution triggered via Argo UI or CLI
- Event-driven pipelines triggered by other workflows
- One-time data processing tasks
- CI/CD integration where external systems trigger execution

**Triggering:**
```bash
# Submit the workflow manually
argo submit workflow.yaml

# Or trigger via kubectl
kubectl create -f workflow.yaml
```

#### CronWorkflow (Scheduled Execution)

Set a cron schedule string to create a **CronWorkflow** for recurring execution:

```yaml
workflows:
  my-cron-workflow:
    name: my-scheduled-pipeline
    schedule: "0 4 * * *"  # Creates a CronWorkflow that runs daily at 4 AM
```

**Use cases:**
- Regularly scheduled data ingestion
- Periodic model training or evaluation
- Automated report generation
- Scheduled data synchronization

**Common cron schedules:**
- `"0 4 * * *"` - Daily at 4 AM
- `"*/15 * * * *"` - Every 15 minutes
- `"0 0 * * 0"` - Weekly on Sundays at midnight
- `"0 0 1 * *"` - Monthly on the 1st at midnight


### Configuration Reference

#### Workflow-Level Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | `wurzel` | Name of the Workflow/CronWorkflow |
| `namespace` | string | `argo-workflows` | Kubernetes namespace |
| `schedule` | string | `0 4 * * *` | Cron schedule for CronWorkflow. Set to `null` to create a normal Workflow instead |
| `entrypoint` | string | `wurzel-pipeline` | DAG entrypoint name |
| `serviceAccountName` | string | `wurzel-service-account` | Kubernetes service account |
| `dataDir` | path | `/usr/app` | Data directory inside containers |
| `annotations` | map | `{}` | Workflow-level annotations |
| `podSpecPatch` | string | `null` | Custom pod spec patch (YAML string) |

#### Pod Security Context Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `runAsNonRoot` | bool | `true` | Require non-root user |
| `runAsUser` | int | `null` | UID to run as |
| `runAsGroup` | int | `null` | GID to run as |
| `fsGroup` | int | `null` | Filesystem group |
| `fsGroupChangePolicy` | string | `null` | `Always` or `OnRootMismatch` |
| `supplementalGroups` | list[int] | `[]` | Additional group IDs |
| `seccompProfileType` | string | `RuntimeDefault` | Seccomp profile type |

#### Container Security Context Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `runAsNonRoot` | bool | `true` | Require non-root user |
| `runAsUser` | int | `null` | UID to run as |
| `runAsGroup` | int | `null` | GID to run as |
| `allowPrivilegeEscalation` | bool | `false` | Allow privilege escalation |
| `readOnlyRootFilesystem` | bool | `null` | Read-only root filesystem |
| `dropCapabilities` | list[str] | `["ALL"]` | Linux capabilities to drop |
| `seccompProfileType` | string | `RuntimeDefault` | Seccomp profile type |

#### Container Resources Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cpu_request` | string | `100m` | CPU request |
| `cpu_limit` | string | `500m` | CPU limit |
| `memory_request` | string | `128Mi` | Memory request |
| `memory_limit` | string | `512Mi` | Memory limit |

#### Tokenizer Cache Options

The tokenizer cache configuration allows you to mount a PersistentVolumeClaim (PVC) containing pre-downloaded HuggingFace tokenizer models. This is useful for:

- Avoiding repeated model downloads in air-gapped environments
- Reducing startup time by using cached models
- Sharing model cache across workflow runs

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Enable tokenizer cache volume mount |
| `claimName` | string | `tokenizer-cache-pvc` | PVC name for existing PVC (when `createPvc: false`) |
| `mountPath` | string | `/cache/huggingface` | Mount path inside container |
| `readOnly` | bool | `true` | Mount as read-only |
| `createPvc` | bool | `false` | Create PVC via `volumeClaimTemplates` (workflow-scoped) |
| `storageSize` | string | `10Gi` | Storage size (when `createPvc: true`) |
| `storageClassName` | string | `null` | Storage class name (when `createPvc: true`) |
| `accessModes` | list[str] | `["ReadWriteOnce"]` | Access modes (when `createPvc: true`) |

When enabled, the `HF_HOME` environment variable is automatically set to the `mountPath`, directing HuggingFace libraries to use the cached models.

!!! note "createPvc vs claimName"
    - **`createPvc: false`** (default): Uses an existing PVC specified by `claimName`. You must create the PVC separately.
    - **`createPvc: true`**: Creates a workflow-scoped PVC via Argo's `volumeClaimTemplates`. The PVC is created when the workflow starts and deleted when it completes. This is useful for temporary caches but **not** for persistent model storage across runs.

#### S3 Artifact Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bucket` | string | `wurzel-bucket` | S3 bucket name |
| `endpoint` | string | `s3.amazonaws.com` | S3 endpoint URL |
| `defaultMode` | int | `null` | File permissions (decimal) |

### Middleware Configuration

Middlewares (like Prometheus for metrics collection) are configured via environment variables in the `container.env` section. Middlewares must be enabled and configured at **generate-time** in your `values.yaml` file.

#### Enabling Prometheus Middleware

To enable Prometheus middleware for metrics collection, add the following to your `container.env` section:

```yaml
container:
  env:
    # Enable Prometheus middleware
    MIDDLEWARES: "prometheus"
    PROMETHEUS__PROMETHEUS_GATEWAY: "prometheus-pushgateway.monitoring.svc.cluster.local:9091"

    # Optional Prometheus settings
    PROMETHEUS__PROMETHEUS_JOB: "wurzel-pipeline"
    PROMETHEUS__PROMETHEUS_DISABLE_CREATED_METRIC: "true"
```

**Available Prometheus Settings:**

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MIDDLEWARES` | - | Comma-separated list of middleware names (e.g., `"prometheus"`) |
| `PROMETHEUS__PROMETHEUS_GATEWAY` | `localhost:9091` | Prometheus Pushgateway endpoint (host:port) |
| `PROMETHEUS__PROMETHEUS_JOB` | `default-job-name` | Job name for Prometheus metrics |
| `PROMETHEUS__PROMETHEUS_DISABLE_CREATED_METRIC` | `true` | Disable `*_created` metrics |

**Metrics Collected:**

- `step_duration_seconds` - Histogram of step execution duration
- `step_executions_total` - Counter of step executions
- Labels: `step_name`, `run_id` (from `WURZEL_RUN_ID`)

For more details on middlewares, see the [Middleware Documentation](../executor/middlewares.md).

### Runtime Environment Variables

Step settings are configured via environment variables at **runtime** (when the workflow executes). These can be set in three ways:

1. **Inline in `container.env`**: Directly in the values file
2. **Via Kubernetes Secrets**: Using `secretRef` or `envFrom` with `kind: secret`
3. **Via Kubernetes ConfigMaps**: Using `configMapRef` or `envFrom` with `kind: configMap`

```yaml
container:
  # Option 1: Inline environment variables
  env:
    MANUALMARKDOWNSTEP__FOLDER_PATH: "examples/pipeline/demo-data"

  # Option 2: From Secrets/ConfigMaps with optional prefix
  envFrom:
    - kind: secret
      name: wurzel-secrets
      prefix: ""  # No prefix
      optional: true

  # Option 3: Reference entire Secret/ConfigMap
  secretRef:
    - "wurzel-secrets"
  configMapRef:
    - "wurzel-config"
```

!!! tip "Inspecting Required Environment Variables"
    Use `wurzel inspect` to see all environment variables required by your pipeline steps:
    ```bash
    wurzel inspect examples.pipeline.pipelinedemo:pipeline --gen-env
    ```

### Programmatic Usage

Use the Argo backend directly in Python:

```python
from pathlib import Path
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

# Generate Argo Workflows configuration from values file
backend = ArgoBackend.from_values(
    files=[Path("values.yaml")],
    workflow_name="pipelinedemo"
)
argo_yaml = backend.generate_artifact(pipeline)
print(argo_yaml)
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

## Multiple Values Files

You can use multiple values files for environment-specific overrides:

```bash
# Base configuration + environment-specific overrides
wurzel generate --backend ArgoBackend \
    --values base-values.yaml \
    --values production-values.yaml \
    --pipeline_name pipelinedemo \
    --output cronworkflow.yaml \
    examples.pipeline.pipelinedemo:pipeline
```

Later files override earlier ones using deep merge semantics.

## Prerequisites

- Kubernetes cluster with Argo Workflows installed
- kubectl configured to access your cluster
- Appropriate RBAC permissions for workflow execution
- S3-compatible storage for artifacts (optional but recommended)
- A `values.yaml` file for generate-time configuration

## Learn More

- [Argo Workflows Documentation](https://argoproj.github.io/argo-workflows/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Back to Backend Overview](./index.md)
