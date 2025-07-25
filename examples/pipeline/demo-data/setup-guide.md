# Setting Up Your RAG Pipeline

This guide walks through the process of setting up a Retrieval-Augmented Generation pipeline using Wurzel.

## Prerequisites

Before you begin, ensure you have:

- Docker installed on your system
- Access to a vector database (Qdrant or Milvus)
- Your documents ready for processing

## Configuration Steps

### Step 1: Prepare Your Documents

Place your markdown files in the `demo-data` directory. Wurzel will automatically discover and process all `.md` files in this location.

### Step 2: Environment Configuration

Set the following environment variables:

```bash
export MANUALMARKDOWNSTEP__FOLDER_PATH=/path/to/your/documents
export WURZEL_PIPELINE=your_pipeline:pipeline
```

### Step 3: Vector Database Setup

Configure your vector database connection:

- **For Qdrant**: Set `QDRANT__URI` and `QDRANT__APIKEY`
- **For Milvus**: Set `MILVUS__URI` and connection parameters

### Step 4: Run the Pipeline

Execute your pipeline using Docker Compose:

```bash
docker-compose up wurzel-pipeline
```

## Pipeline Stages

1. **Document Loading**: Read markdown files from the configured directory
2. **Text Processing**: Clean and split documents into manageable chunks
3. **Embedding Generation**: Create vector embeddings for text chunks
4. **Vector Storage**: Store embeddings in your chosen vector database

## Monitoring and Debugging

- Check DVC status for pipeline execution details
- Review container logs for processing information
- Use the built-in Git integration to track changes
