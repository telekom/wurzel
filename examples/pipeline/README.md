<!--
SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
SPDX-License-Identifier: CC0-1.0
-->
# I am your tutoral to deploy Wurzel!
Lets go through the process of how to get a wurzel pipeline deployed locally.

for that we need the following points:
## Hallo World Wurzel

1. define a pipeline.py where you chain your Step
``` python
from wurzel.steps.embedding import EmbeddingStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.steps.qdrant.step import QdrantConnectorStep
from wurzel.utils import WZ

source = WZ(ManualMarkdownStep)
embedding = WZ(EmbeddingStep)
step = WZ(QdrantConnectorStep)


source >> embedding >> step
pipeline = step

```
2. Build your own Dockerfile based on the tweigeldev/wurzel:beta image
here you can add depdencies where your own files are placed
```Docker
FROM tweigeldev/wurzel:beta
# if your steps are located in other dependencies
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
# add your pipeline definition
COPY pipeline.py .
# adressing the last step
ENV WURZEL_PIPELINE="pipeline:pipeline"
```
5. run the your container in Docker
```
docker build -t my/wurzel examples/pipeline/.
docker docker run -it my/wurzel

```
6. enjoy your pipeline!

## Multi Tenantcy Deployment in Kubernetes with helm scheduled with cronjob
1. Do the same a above but put multiple pipeline defintions into the context of the Docker container
2. This Helm chart will start a dedicated Cronjob with complete seperated data managent with using sperate PersistentVolumeClaims(PWC).
3. use the helm chart in this repo. Adapt the given values.yaml
    By each Tenant configure each step use the config below `TENANTS`. Do not forget to add your active tenants to `ENABLED_TENANTS` as well.

    For the schedule you can configure `.Values.cronschedule` to have the same for all, or override it below your dedicated tenant with `.Values.<TENANT>.cronschedule`

    Select the right pipeline by tenant by specifing  the `.Values.<TENANT>.WURZEL_PIPELINE`.


    To configure DVC or GIT change/introduce them in `.Values.GLOBAL_ENV`

4. deploy this helm chart, wait until the scheudle, or trigger the cronjob manual
5. enjoy the result
