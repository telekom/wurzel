<!--
SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)

SPDX-License-Identifier: Apache-2.0
-->
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

```
pip install wurzel
```

## Usage

Below is a simple example of how wurzel can be used:
### Execute single Step
#### With CLI
ManualMarkdownStep requires a source-folder to be passed by environment-variable:
```sh
MANUALMARKDOWNSTEP__FOLDER_PATH="." wurzel run wurzel.steps.manual_markdown.ManualMarkdownStep
```
Other Steps require other environment-variables. find it out via the Class Definition of the step or by calling :
```sh
wurzel inspect wurzel.steps.manual_markdown.ManualMarkdownStep
```

### Building your one step
#### Building a new WurzelTip(new data source)
A WurzelStep requires Settings[Optional] InputDatacontract[Optional], OutoutDataContract[Mandatory]. Datasources do not have a prerequisite Step, thus the InputDatacontract is *None*.
We are using MarkdownDataContract as the first common contract in document retrieval. Of cause you may define your own.

```python
class MySettings(Settings):
    """Settings fro MyDatasourceStep"""
    YOUR_REQUIRED_ENVIRONMENT: Any

class MyDatasourceStep(TypedStep[MySettings, None,list[MarkdownDataContract]]):
    """Data Source for md files from a configurable path
    """
    def run(self, inpt: None) -> list[MarkdownDataContract]:
        ### your code here
        return result
```
#### Building a new WurzelStep
Of Cause a wurzel is not ony defined by its Tips but also some steps which use the prerequisite output. Like Filters, Validators or Splitter Steps.
```python
class MyFilterStep(TypedStep[MySettings, list[MarkdownDataContract],list[MarkdownDataContract]]):
        def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
            ### your code here
            return result
```
and some Steps which even change the shape of a contract completely. For example from list to DataFrame. The DataFrame shape is enforced by pandera DataframeSchemas.

```python
class MyEmbeddingStep(TypedStep[EmbeddingSettings, list[MarkdownDataContract], DataFrame[EmbeddingResult]]):
    def run(self, inpt: list[MarkdownDataContract]) -> DataFrame[EmbeddingResult]:
        """ Executes the embedding step by processing input markdown files, generating embeddings,
        and saving them to a CSV file.
        """
        ### your code here
        return df
```
The *run* function may be executed multiple times. Each time per previous Step. So if you want to do some preparation only once, like creating tables/collection or connections we recommend to do so in the *__init__*
```python
class MyEmbeddingStep(TypedStep[DatabaseSettings, DataFrame[EmbeddingResult], DataFrame[EmbeddingResult]]):
    def __init__(self):
        ## create table and establish connection here
    def run():
        ## insert data here
```



### Execute existing wurzel
```python

from wurzel.steps import (
    EmbeddingStep,
    QdrantConnectorStep
    )
from wurzel.utils import WZ
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel import TypedStep

def pipeline() -> TypedStep:
    """Pipeline definition"""
    md = WZ(ManualMarkdownStep)
    embed = WZ(EmbeddingStep)
    db = WZ(QdrantConnectorStep)

    md >> embed >> db
    return db

```

## Community

Wurzel is a collaborative project aiming to combine the best ideas in the field of RAG systems. Join us in building the future of retrieval-augmented generation!

### Steps to Contribute
1. Fork this repository.
2. Create a new branch for your feature or bug fix: `git checkout -b feature/feature-name`.
3. Make your changes and commit them: `git commit -m "Add awesome feature"`.
4. Push to your branch: `git push origin feature/feature-name`.
5. Submit a pull request for review.

## Implementation Hints

### Milvus Mock

Milvus provides Milvus lite or Milvus standalone for docker. Unfortunately both does not work in the ci runners.
We decided to skip all Milvus related tests in the pipeline but takeing care of them local and ensure that they can interact with Milvus by running a standalone version of it local.

### qdrant mock
We mainly replaced Milvus with qdrant. Thus we use qdrant in-memory for unittests. Unless makefile is used


## Code of Conduct

This project has adopted the [Contributor Covenant](https://www.contributor-covenant.org/) in version 2.1 as our code of conduct. Please see the details in our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). All contributors must abide by the code of conduct.

By participating in this project, you agree to abide by its [Code of Conduct](./CODE_OF_CONDUCT.md) at all times.

## Licensing

This project follows the [REUSE standard for software licensing](https://reuse.software/).
Each file contains copyright and license information, and license texts can be found in the [./LICENSES](./LICENSES) folder. For more information visit https://reuse.software/.
You can find a guide for developers at https://telekom.github.io/reuse-template/.
