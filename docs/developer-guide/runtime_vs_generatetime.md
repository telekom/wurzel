
# Runtime vs. Generate Time

This document explains the two main phases of a `wurzel` pipeline: **Generate Time** and **Runtime**.

```mermaid
graph LR

subgraph "Compile Time / Generate Time"
    direction TB
    A(Python Code<br><i>e.g., pipeline.py</i>) -- defines --> P(Wurzel Pipeline Object);
    P -- wurzel generate --> C(Backend Configuration<br><i>e.g., Argo Workflow YAML / DVC YAML</i>);
end

subgraph "Runtime"
    direction TB
    C -- submitted to --> R(Execution Backend<br><i>e.g., Argo Workflows </i>);
    R -- executes --> S1(Step 1);
    S1 -- then --> S2(Step 2);
    S2 -- then --> Sn(Step N...);

    subgraph "Anatomy of a Single Step Execution"
        direction TB
        subgraph S1
            S1_Start(Container Start) --> S1_Mounts(Secrets & Volumes<br>are mounted into the container's filesystem);
            S1_Mounts --> S1_Inputs(Input artifacts<br>are downloaded/mounted);
            S1_Inputs --> S1_Code(Step's code/command<br>is executed);
            S1_Code --> S1_Outputs(Output artifacts<br>are uploaded/saved);
            S1_Outputs --> S1_End(Container Stop);
        end
    end
end

classDef compile fill:#E6F3FF,stroke:#007BFF,color:#000;
classDef runtime fill:#E8F5E9,stroke:#4CAF50,color:#000;
classDef step fill:#FFF3E0,stroke:#FF9800,color:#000;

class A,P,C compile;
class R,S1,S2,Sn runtime;
class S1_Start,S1_Mounts,S1_Inputs,S1_Code,S1_Outputs,S1_End step;

```

## Key Concepts

### Generate Time (or Compile Time)
-   **What it is:** This is the phase where your Python pipeline definition is converted into a concrete, executable workflow for a specific backend (like Argo Workflows or DVC).
-   **Trigger:** You run the `wurzel generate` command.
-   **Input:** Your Python script containing a `wurzel` pipeline definition.
-   **Output:** A configuration file (e.g., a `.yaml` file for Argo) that describes every step, their dependencies, the container images to use, and the commands to run.

### Runtime
-   **What it is:** This is the phase where the pipeline is actually executed by the backend.
-   **Trigger:** You submit the generated configuration file to the backend (e.g., using `argo submit` or `dvc repro`).
-   **Process:** The backend reads the workflow and executes the steps in the correct order.
-   **Important Aspects during a Step's Runtime:**
    -   **Containerization:** Each step typically runs in its own isolated container.
    -   **Secret Mounting:** Before your code runs, the backend mounts secrets (like API keys or database credentials) and configurations securely into the container's filesystem. Your code can then read them as if they were local files.
    -   **Data I/O:** The step downloads its necessary input artifacts, executes its logic, and uploads its resulting output artifacts.
