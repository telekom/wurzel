| Module Name           | Purpose                              | Avg Execution Time (s) | Description                                                                                              |
| --------------------- | ------------------------------------ | ---------------------- | -------------------------------------------------------------------------------------------------------- |
| DataIngestor          | Load raw data from sources           | 5.2                    | Connects to various data sources (APIs, databases, flat files) and loads raw, unprocessed data streams. |
| SchemaInferencer      | Infer structure and schema           | 3.1                    | Analyzes raw data to automatically determine data types, structures, and inter-field relationships.      |
| EntityResolver        | Resolve entity duplicates            | 7.6                    | Uses fuzzy logic and ML techniques to merge similar records referring to the same real-world entity.     |
| OntologyTagger        | Semantic tagging                     | 4.4                    | Enriches records by tagging entities and concepts based on a predefined or custom ontology.              |
| RelationshipMapper    | Link related data entities           | 6.3                    | Identifies and maps relationships between different data entities to build a coherent knowledge graph.   |
| DataCleaner           | Clean and normalize data             | 2.5                    | Removes duplicates, handles nulls, standardizes formats, and ensures consistency in datasets.            |
