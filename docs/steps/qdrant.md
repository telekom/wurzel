::: wurzel.steps.qdrant.step

## Qdrant Collection Retirement

To avoid unbounded growth of collections, the `QdrantConnectorStep` implements logic to retire (delete) older collections based on usage and aliasing.

**Retention Rules:**

- Retains the most recent `COLLECTION_HISTORY_LEN` versioned collections.
- Skips deletion if collection is aliased.
- Skips deletion if collection was accessed within `COLLECTION_USAGE_RETENTION_DAYS`.

**Configuration Flags:**

| Setting                           | Description                                                              |
|-----------------------------------|--------------------------------------------------------------------------|
| `COLLECTION_HISTORY_LEN`          | Number of latest versions to retain                                      |
| `COLLECTION_USAGE_RETENTION_DAYS` | Protects recently accessed collections from deletion                     |
| `COLLECTION_RETIRE_DRY_RUN`       | When `true`, only logs deletions; doesn’t actually delete anything       |
| `ENABLE_COLLECTION_RETIREMENT`    | When `false`, disables retirement logic entirely (no deletion performed) |
| `TELEMETRY_DETAILS_LEVEL`         | Controls how detailed the telemetry info fetched from Qdrant should be.  |


::: wurzel.steps.qdrant.step_multi_vector

::: wurzel.steps.qdrant.settings
