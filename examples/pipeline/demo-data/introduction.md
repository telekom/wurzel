# Introduction to Wurzel

Welcome to Wurzel, an advanced ETL framework designed specifically for Retrieval-Augmented Generation (RAG) systems.

## What is Wurzel?

Wurzel is a Python library that streamlines the process of building data pipelines for RAG applications. It provides:

- **Type-safe pipeline definitions** using Pydantic and Pandera
- **Modular step architecture** for easy composition and reuse
- **Built-in support** for popular vector databases like Qdrant and Milvus
- **Cloud-native deployment** capabilities with Docker and Kubernetes
- **DVC integration** for data versioning and pipeline orchestration

## Key Features

### Pipeline Composition
Build complex data processing pipelines by chaining simple, reusable steps together.

### Vector Database Support
Out-of-the-box integration with:
- Qdrant for high-performance vector search
- Milvus for scalable vector databases
- Easy extension for other vector stores

### Document Processing
Advanced document processing capabilities including:
- PDF extraction with Docling
- Markdown processing and splitting
- Text embedding generation
- Duplicate detection and removal

## Getting Started

To create your first Wurzel pipeline:

1. Define your data processing steps
2. Chain them together using the `>>` operator
3. Configure your environment variables
4. Run with DVC or Argo Workflows

This demo shows a simple pipeline that processes markdown documents and prepares them for vector storage.
