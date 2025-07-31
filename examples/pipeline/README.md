# Wurzel Pipeline Demo

This demo showcases a complete Wurzel pipeline that processes markdown documents for RAG applications.

## Quick Start

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up wurzel-pipeline
   ```

2. **Or build manually with platform flag:**
   ```bash
   docker build --platform linux/amd64 -f ../../Dockerfile -t test_wurzel ../../
   docker-compose up wurzel-pipeline
   ```

## What This Demo Does

The pipeline performs the following steps:

1. **Document Loading**: Reads all `.md` files from the `demo-data/` directory
2. **Text Processing**: Processes and prepares the markdown content
3. **Pipeline Execution**: Runs the complete Wurzel pipeline using DVC

## Demo Files

- `demo-data/`: Contains example markdown files
  - `introduction.md`: Overview of Wurzel framework
  - `setup-guide.md`: Guide for setting up RAG pipelines
  - `architecture.md`: Technical architecture documentation
- `output/`: Directory for pipeline outputs
- `docker-compose.yml`: Container orchestration configuration
- `pipelinedemo.py`: Simple pipeline definition

## Environment Variables

The demo is configured with:

- `MANUALMARKDOWNSTEP__FOLDER_PATH=/usr/app/demo-data`: Points to the demo documents
- `WURZEL_PIPELINE=pipelinedemo:pipeline`: Specifies which pipeline to run

## Extending the Demo

To add more documents:
1. Place additional `.md` files in the `demo-data/` directory
2. Restart the pipeline: `docker-compose restart wurzel-pipeline`

To modify the pipeline:
1. Edit `pipelinedemo.py` to add more steps
2. Rebuild the image: `docker-compose build wurzel-pipeline`

## Troubleshooting

- Check container logs: `docker-compose logs wurzel-pipeline`
- Verify file permissions on `demo-data/` and `output/` directories
- Ensure Docker has enough resources allocated for the build process

---

# Original Tutorial: Deploying Wurzel

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
