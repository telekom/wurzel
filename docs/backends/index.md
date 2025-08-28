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

## Getting Started

Ready to leverage the power of backends? Check out our [CLI Usage Guide](../backends.md#cli-usage) or dive into the specific backend documentation for your target platform.
