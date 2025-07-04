[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/telekom/wurzel/actions)
[![Docs](https://img.shields.io/badge/docs-live-brightgreen)](https://telekom.github.io/wurzel/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![License MIT](https://img.shields.io/github/license/docling-project/docling)](https://reuse.software/)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)

# wurzel
<img src=https://raw.githubusercontent.com/telekom/wurzel/main/docs/icon.png width=20% align=right>


wurzel is the german word for [root](https://en.wikipedia.org/wiki/Root). So with this framework we provide a combination of the best out of the whole domain of retrieval and beyond.

wurzel is an open-source Python library built to address advanced **Extract, Transform, Load (ETL)** needs for **Retrieval-Augmented Generation (RAG)** systems. It is designed to streamline ETL processes while offering essential features like **multi-tenancy**, **cloud-native deployment support**, and **job scheduling**.

The repository includes initial implementations for widely-used frameworks in the RAG ecosystem, such as Qdrant, Milvus, and Hugging Face, providing users with a strong starting point for building scalable and efficient RAG pipelines.

## Features

- **Advanced ETL Pipelines**: Tailored for the specific needs of RAG systems.
- **Multi-Tenancy**: Easily manage multiple tenants or projects within a single system.
- **Cloud-Native Deployment**: Designed for seamless integration with Kubernetes, Docker, and other cloud platforms.
- **Scheduling Capabilities**: Schedule and manage ETL tasks using built-in or external tools.
- **Framework Integrations**: Pre-built support for popular tools like Qdrant, Milvus, and Hugging Face.
- **Type Security**: By leveraging capabilities of [pydantic](https://docs.pydantic.dev/latest/) and [pandera](https://pandera.readthedocs.io/en/stable/) we ensure type security

## Installation

To get started with wurzel, install the library using pip:

```bash
pip install wurzel
```


## Run a Step (Two Ways)

### 1. CLI-based Execution
Run a step using the CLI:
```bash
wurzel run <step_file_path> --inputs ./data --output ./out
```
To inspect the step requirements:
```bash
wurzel inspect wurzel.<step_path>
```
### 2. Programmatic Execution (Python)
Run a step using the snippet below:
```bash
from wurzel.steps import step
from pathlib import Path
from wurzel.step_executor import BaseStepExecutor

with BaseStepExecutor() as ex:
    ex(step, Path("./input"), Path("./output"))
```

### Building your one step

For detailed instructions and examples on how to use wurzel, please refer to our [official documentation](https://telekom.github.io/wurzel/).

## Code of Conduct

This project has adopted the [Contributor Covenant](https://www.contributor-covenant.org/) in version 2.1 as our code of conduct. Please see the details in our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). All contributors must abide by the code of conduct.

By participating in this project, you agree to abide by its [Code of Conduct](./CODE_OF_CONDUCT.md) at all times.

## Licensing

This project follows the [REUSE standard for software licensing](https://reuse.software/).
Each file contains copyright and license information, and license texts can be found in the [./LICENSES](./LICENSES) folder. For more information visit https://reuse.software/.
You can find a guide for developers at https://telekom.github.io/reuse-template/.
