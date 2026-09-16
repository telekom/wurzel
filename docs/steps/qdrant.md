::: wurzel.steps.qdrant.step
    handler: python

## Qdrant Collection Retirement

To avoid unbounded growth of collections, the `QdrantConnectorStep` retires (deletes) older versioned collections based on history length and aliases only.

Qdrant telemetry `last_responded` is not used: cluster events can refresh that stamp when `searches.count` is 0, which blocked deletion of unused collections.

**Retention Rules:**

- Retains the most recent `COLLECTION_HISTORY_LEN` versioned collections.
- Skips deletion if collection is aliased.
- The live collection is protected by its alias (for example `austria` → `austria_vN`).

**Configuration Flags:**

| Setting                           | Description                                                              |
|-----------------------------------|--------------------------------------------------------------------------|
| `COLLECTION_HISTORY_LEN`          | Number of latest versions to retain                                      |
| `COLLECTION_RETIRE_DRY_RUN`       | When `true`, only logs deletions; doesn’t actually delete anything       |
| `ENABLE_COLLECTION_RETIREMENT`    | When `false`, disables retirement logic entirely (no deletion performed) |


::: wurzel.steps.qdrant.step_multi_vector
    handler: python

::: wurzel.steps.qdrant.settings
    handler: python
