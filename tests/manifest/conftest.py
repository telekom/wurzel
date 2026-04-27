# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

MINIMAL_MANIFEST_YAML = """\
apiVersion: wurzel.dev/v1alpha1
kind: Pipeline
metadata:
  name: test-pipeline
spec:
  backend: dvc
  steps:
    - name: source
      class: wurzel.steps.manual_markdown.ManualMarkdownStep
      settings:
        FOLDER_PATH: ./data
"""

FULL_MANIFEST_YAML = """\
apiVersion: wurzel.dev/v1alpha1
kind: Pipeline
metadata:
  name: full-pipeline
  labels:
    team: platform
spec:
  backend: argo
  schedule: "0 4 * * 1"
  middlewares:
    - name: secret_resolver
      settings: {}
    - name: prometheus
      settings:
        GATEWAY: "pushgateway.svc:9091"
        JOB: "my-pipeline"
  steps:
    - name: source
      class: wurzel.steps.manual_markdown.ManualMarkdownStep
      settings:
        FOLDER_PATH: ./data
        API_KEY: "${secret:vault:my-api-key}"
    - name: splitter
      class: wurzel.steps.splitter.SimpleSplitterStep
      dependsOn:
        - source
      settings:
        BATCH_SIZE: "100"
        DB_PASS: "${secret:k8s:my-db-secret/password}"
    - name: merger
      class: wurzel.steps.merger.MergerStep
      dependsOn:
        - source
        - splitter
      settings: {}
  backendConfig:
    argo:
      namespace: argo-workflows
      serviceAccountName: wurzel-sa
      container:
        image: ghcr.io/telekom/wurzel
    dvc:
      dataDir: ./data
      encapsulateEnv: true
"""
