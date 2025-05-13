# I am your tutorial to deploy Wurzel!

Let's go through the process of how to get a Wurzel pipeline deployed locally.

For that, we need the following steps:

## Hello World Wurzel
1. Define a `pipeline.py` where you chain your steps:
```python
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
2. Build your own Dockerfile based on the [ghcr.io/telekom/wurzel:](https://github.com/telekom/wurzel/pkgs/container/wurzel) image. Here you can add dependencies where your own files are placed, either pass them directly or within the `requirements.txt`:
```Dockerfile
FROM ghcr.io/telekom/wurzel:latest
# if your steps are located in other dependencies
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
# add your pipeline definition
COPY pipeline.py .
# addressing the last step
ENV WURZEL_PIPELINE="pipeline:pipeline"
```
3. Run your container in Docker:
```
docker build -t my/wurzel examples/pipeline/.
docker run -it my/wurzel
```
4. Enjoy your pipeline!

## Multi-Tenancy Deployment in Kubernetes with Helm Scheduled with CronJob

1. Do the same as above but put multiple pipeline definitions into the context of the Docker container.
2. This Helm chart will start a dedicated CronJob with completely **separated** data **management**, using **separate** PersistentVolumeClaims (PVC).
3. Use the Helm chart in this repo. Adapt the given `values.yaml`.

   - For each tenant, configure each step using the config below `TENANTS`. Do not forget to add your active tenants to `ENABLED_TENANTS` as well.
   - For the schedule, you can configure `.Values.cronschedule` to have the same schedule for all, or override it for a specific tenant using `.Values.<TENANT>.cronschedule`.
   - Select the right pipeline per tenant by **specifying** `.Values.<TENANT>.WURZEL_PIPELINE`.
   - To configure DVC or Git, modify or introduce them in `.Values.GLOBAL_ENV`.

4. Deploy this Helm chart, wait until the **scheduled** execution, or trigger the CronJob **manually**.
5. Enjoy the result!
