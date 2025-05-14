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


## With CLI

ManualMarkdownStep requires a source-folder to be passed by environment-variable:

```sh
MANUALMARKDOWNSTEP__FOLDER_PATH="." wurzel run wurzel.steps.manual_markdown.ManualMarkdownStep
```

Other Steps require other environment-variables. find it out via the Class Definition of the step or by calling:

```sh
wurzel inspect wurzel.steps.manual_markdown.ManualMarkdownStep
```

### Building your one step

For detailed instructions and examples on how to use wurzel, please refer to our [official documentation](https://telekom.github.com/wurzel/).

## Code of Conduct

This project has adopted the [Contributor Covenant](https://www.contributor-covenant.org/) in version 2.1 as our code of conduct. Please see the details in our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). All contributors must abide by the code of conduct.

By participating in this project, you agree to abide by its [Code of Conduct](./CODE_OF_CONDUCT.md) at all times.

## Licensing

This project follows the [REUSE standard for software licensing](https://reuse.software/).
Each file contains copyright and license information, and license texts can be found in the [./LICENSES](./LICENSES) folder. For more information visit https://reuse.software/.
You can find a guide for developers at https://telekom.github.io/reuse-template/.
