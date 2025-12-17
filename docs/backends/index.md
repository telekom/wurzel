# Backend Architecture in Wurzel

## What are Backends?

Backends in Wurzel are powerful abstractions that transform your pipeline definitions into executable configurations for different orchestration platforms. Think of them as translators that take your high-level pipeline logic and convert it into the specific format required by your target execution environment.

## Why Backends are Great

### 🚀 **Write Once, Deploy Anywhere**

Define your data pipeline logic once using Wurzel's intuitive API, then deploy it to multiple platforms without rewriting code. Whether you need local development with DVC, cloud-native execution with Argo Workflows, or future platforms like GitHub Actions - your pipeline logic remains the same.

### 🔧 **Platform-Specific Optimization**

Each backend is specifically designed to leverage the unique capabilities of its target platform:

- **DVC Backend**: Optimizes for data versioning, experiment tracking, and reproducible ML workflows
- **Argo Backend**: Leverages Kubernetes-native features like horizontal scaling, resource management, and cloud-native scheduling

### 🎯 **Environment-Aware Configuration**

Backends automatically handle environment-specific concerns:

- Container orchestration and resource allocation
- Storage and artifact management
- Scheduling and triggering mechanisms
- Security and access control integration

### 📈 **Scalability Without Complexity**

Start with simple local execution and seamlessly scale to enterprise-grade orchestration platforms. Backends abstract away the complexity of different deployment targets while preserving the power and flexibility of each platform.

## How Backends Work

1. **Pipeline Definition**: You define your pipeline using Wurzel's step classes and the `WZ` utility
2. **Backend Selection**: Choose the appropriate backend for your target environment
3. **Code Generation**: The backend generates platform-specific configuration files
4. **Execution**: Deploy and run using the native tools of your chosen platform

## Generate-Time vs Runtime Configuration

Wurzel backends use a **two-phase configuration model** that separates concerns:

### Generate-Time Configuration (YAML)

At generate-time (`wurzel generate`), a `values.yaml` file configures the **infrastructure and workflow structure**:

- Container images and registries
- Kubernetes namespaces and service accounts
- Cron schedules and triggers
- Security contexts and resource limits
- Artifact storage (S3 buckets, endpoints)
- Data directories

This configuration is baked into the generated artifacts (e.g., `cronworkflow.yaml`, `dvc.yaml`).

### Runtime Configuration (Environment Variables)

At runtime (when the pipeline executes), **step settings** are read from environment variables:

- `MANUALMARKDOWNSTEP__FOLDER_PATH` - where to read markdown files
- `SIMPLESPLITTERSTEP__BATCH_SIZE` - processing batch size
- `EMBEDDINGSTEP__MODEL_NAME` - which embedding model to use

These can be changed without regenerating the workflow artifacts.

### Why This Separation?

| Aspect | Generate-Time (YAML) | Runtime (Env Vars) |
|--------|---------------------|--------------------|
| **When applied** | `wurzel generate` | Pipeline execution |
| **What it configures** | Infrastructure, workflow structure | Step behavior, business logic |
| **Change frequency** | Rarely (infra changes) | Often (per environment) |
| **Examples** | Container image, namespace, schedule | Model paths, batch sizes, API keys |

This allows you to:

- Generate workflow artifacts once and deploy to multiple environments
- Store sensitive runtime config in Kubernetes Secrets
- Change step behavior without rebuilding containers or regenerating workflows

## Available Backends

- **[DVC Backend](dvc.md)**: For data versioning and ML experiment tracking
- **[Argo Workflows Backend](argoworkflows.md)**: For Kubernetes-native pipeline orchestration

## Future Backends

Wurzel's extensible architecture supports adding new backends for:

- **GitLab CI/CD**: For generating `.gitlab-ci.yml` pipelines
- **GitHub Actions**: To produce `workflow.yml` for GitHub-native automation
- **Apache Airflow**: For DAG-based orchestration and scheduling
- **LocalBackend**: Execute steps locally without an external orchestrator
- **Kubernetes CronJobs**: Direct Kubernetes-native `CronJob` manifests
