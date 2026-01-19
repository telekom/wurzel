# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""GitLab CI/CD backend that renders pipelines from YAML values."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from wurzel.backend.backend import Backend
from wurzel.backend.values import load_values
from wurzel.cli import generate_cli_call
from wurzel.step import TypedStep
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor


class GitlabArtifactConfig(BaseModel):
    """Configuration for GitLab CI/CD artifacts."""

    paths: list[str] = Field(default_factory=lambda: ["data/"])
    expire_in: str = "1 week"
    when: str = "on_success"


class GitlabImageConfig(BaseModel):
    """Container image configuration for GitLab CI/CD."""

    name: str = "ghcr.io/telekom/wurzel:latest"
    pull_policy: str | None = None


class GitlabVariablesConfig(BaseModel):
    """Environment variables configuration."""

    variables: dict[str, str] = Field(default_factory=dict)


class GitlabCacheConfig(BaseModel):
    """Cache configuration for GitLab CI/CD."""

    paths: list[str] = Field(default_factory=list)
    key: str = "${CI_COMMIT_REF_SLUG}"
    policy: str = "pull-push"


class GitlabJobConfig(BaseModel):
    """Job-level configuration options."""

    stage: str = "process"
    tags: list[str] = Field(default_factory=list)
    timeout: str | None = None
    retry: int | dict[str, Any] = 0
    allow_failure: bool = False
    rules: list[dict[str, Any]] = Field(default_factory=list)
    before_script: list[str] = Field(default_factory=list)
    after_script: list[str] = Field(default_factory=list)


class GitlabConfig(BaseModel):
    """GitLab pipeline configuration from YAML values."""

    dataDir: Path = Path("./data")
    encapsulateEnv: bool = True
    image: GitlabImageConfig = Field(default_factory=GitlabImageConfig)
    variables: dict[str, str] = Field(default_factory=dict)
    cache: GitlabCacheConfig = Field(default_factory=GitlabCacheConfig)
    artifacts: GitlabArtifactConfig = Field(default_factory=GitlabArtifactConfig)
    defaultJob: GitlabJobConfig = Field(default_factory=GitlabJobConfig)
    stages: list[str] = Field(default_factory=lambda: ["process"])


class GitlabTemplateValues(BaseModel):
    """YAML values file parsed into strongly typed configuration for GitLab."""

    gitlab: dict[str, GitlabConfig] = Field(default_factory=dict)


def select_pipeline(values: GitlabTemplateValues, pipeline_name: str | None) -> GitlabConfig:
    """Select a pipeline configuration either by name or falling back to the first entry."""
    if pipeline_name:
        try:
            return values.gitlab[pipeline_name]
        except KeyError as exc:
            raise ValueError(f"pipeline '{pipeline_name}' not found in values") from exc
    if values.gitlab:
        first_key = next(iter(values.gitlab))
        return values.gitlab[first_key]
    return GitlabConfig()


class GitlabBackend(Backend):
    """GitLab CI/CD-specific backend implementation for the Wurzel abstraction layer.

    This adapter generates GitLab CI/CD-compatible `.gitlab-ci.yml` files from typed step definitions.
    It recursively resolves all step dependencies and constructs jobs for GitLab CI/CD execution.

    Args:
        config (GitlabConfig | None): Optional config from YAML values.
        executor (BaseStepExecutor): Executor class used to wrap the CLI call.

    """

    @classmethod
    def is_available(cls) -> bool:
        """GitLab backend has no optional dependencies."""
        return True

    def __init__(
        self,
        config: GitlabConfig | None = None,
        *,
        executor: type[BaseStepExecutor] = PrometheusStepExecutor,
    ) -> None:
        super().__init__()
        self.executor: type[BaseStepExecutor] = executor
        self.config = config or GitlabConfig()

    @classmethod
    def from_values(cls, files: Iterable[Path], workflow_name: str | None = None) -> GitlabBackend:
        """Instantiate the backend from values files."""
        values = load_values(files, GitlabTemplateValues)
        config = select_pipeline(values, workflow_name)
        return cls(config=config)

    def _generate_dict(
        self,
        step: TypedStep,
    ) -> dict[str, Any]:
        """Recursively generates a dictionary representing a full GitLab CI/CD pipeline,
        including all dependencies of the given step.

        Each step is represented as a job in the GitLab pipeline, with corresponding
        script commands, dependencies, and artifacts.

        Args:
            step (TypedStep): The root step from which to generate the pipeline DAG.

        Returns:
            dict[str, Any]: A dictionary mapping job names to their GitLab CI/CD job configurations.

        """
        result: dict[str, Any] = {}
        dependencies: list[str] = []

        # Recursively process required steps
        for req_step in step.required_steps:
            dep_result = self._generate_dict(req_step)
            result |= dep_result
            dependencies.append(req_step.__class__.__name__)

        # Generate output path for this step
        output_path = self.config.dataDir / step.__class__.__name__

        # Generate CLI command
        cmd = generate_cli_call(
            step.__class__,
            inputs=[self.config.dataDir / dep for dep in dependencies],
            output=output_path,
            executor=self.executor,
            encapsulate_env=self.config.encapsulateEnv,
        )

        # Build job configuration
        job_config: dict[str, Any] = {
            "stage": self.config.defaultJob.stage,
            "script": [cmd],
            "artifacts": {
                "paths": [str(output_path)],
                "expire_in": self.config.artifacts.expire_in,
                "when": self.config.artifacts.when,
            },
        }

        # Add dependencies if any
        if dependencies:
            job_config["needs"] = dependencies

        # Add tags if configured
        if self.config.defaultJob.tags:
            job_config["tags"] = self.config.defaultJob.tags

        # Add timeout if configured
        if self.config.defaultJob.timeout:
            job_config["timeout"] = self.config.defaultJob.timeout

        # Add retry if configured
        if self.config.defaultJob.retry:
            job_config["retry"] = self.config.defaultJob.retry

        # Add allow_failure if configured
        if self.config.defaultJob.allow_failure:
            job_config["allow_failure"] = self.config.defaultJob.allow_failure

        # Add rules if configured
        if self.config.defaultJob.rules:
            job_config["rules"] = self.config.defaultJob.rules

        # Add before_script if configured
        if self.config.defaultJob.before_script:
            job_config["before_script"] = self.config.defaultJob.before_script

        # Add after_script if configured
        if self.config.defaultJob.after_script:
            job_config["after_script"] = self.config.defaultJob.after_script

        return result | {step.__class__.__name__: job_config}

    def generate_artifact(
        self,
        step: TypedStep,
    ) -> str:
        """Converts the full step graph into a valid `.gitlab-ci.yml` file content.

        Args:
            step (TypedStep): Root step of the pipeline.

        Returns:
            str: A YAML string containing the full GitLab CI/CD pipeline definition.

        """
        # Generate jobs from step graph
        jobs = self._generate_dict(step)

        # Build the complete pipeline configuration
        pipeline: dict[str, Any] = {}

        # Add image configuration
        if self.config.image:
            pipeline["image"] = self.config.image.name
            if self.config.image.pull_policy:
                pipeline["image"] = {
                    "name": self.config.image.name,
                    "pull_policy": self.config.image.pull_policy,
                }

        # Add variables
        if self.config.variables:
            pipeline["variables"] = self.config.variables

        # Add cache configuration
        if self.config.cache.paths:
            pipeline["cache"] = {
                "paths": self.config.cache.paths,
                "key": self.config.cache.key,
                "policy": self.config.cache.policy,
            }

        # Add stages
        pipeline["stages"] = self.config.stages

        # Add all jobs
        pipeline.update(jobs)

        return yaml.dump(pipeline, sort_keys=False)
