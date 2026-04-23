# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.manifest.builder import ManifestBuilder
from wurzel.manifest.models import Metadata, PipelineManifest, PipelineSpec, StepSpec


def _manifest(*step_dicts) -> PipelineManifest:
    return PipelineManifest(
        metadata=Metadata(name="test"),
        spec=PipelineSpec(
            backend="dvc",
            steps=[StepSpec.model_validate(s) for s in step_dicts],
        ),
    )


class TestImportStepClass:
    def test_imports_known_step(self):
        cls = ManifestBuilder.import_step_class("wurzel.steps.manual_markdown.ManualMarkdownStep")
        from wurzel.steps.manual_markdown import ManualMarkdownStep  # noqa: PLC0415

        assert cls is ManualMarkdownStep

    def test_unknown_module_raises(self):
        with pytest.raises(ImportError):
            ManifestBuilder.import_step_class("nonexistent.module.Step")

    def test_unknown_class_in_valid_module_raises(self):
        with pytest.raises(ImportError):
            ManifestBuilder.import_step_class("wurzel.steps.manual_markdown.NoSuchStep")

    def test_non_typed_step_class_raises(self):
        # str is a real class in a valid module but is not a TypedStep subclass
        with pytest.raises(ImportError, match="TypedStep"):
            ManifestBuilder.import_step_class("builtins.str")

    def test_non_class_symbol_raises(self):
        # os.path.join is a function, not a class
        with pytest.raises(ImportError, match="not a class"):
            ManifestBuilder.import_step_class("os.path.join")


class TestBuildStepGraph:
    def test_single_source_step(self):
        manifest = _manifest({"name": "src", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"})
        graph = ManifestBuilder(manifest).build_step_graph()
        assert "src" in graph

    def test_linear_chain_wired(self):
        manifest = _manifest(
            {"name": "src", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"},
            {
                "name": "split",
                "class": "wurzel.steps.splitter.SimpleSplitterStep",
                "dependsOn": ["src"],
            },
        )
        graph = ManifestBuilder(manifest).build_step_graph()
        src_step = graph["src"]
        split_step = graph["split"]
        assert src_step in split_step.required_steps

    def test_fan_in_wired(self):
        manifest = _manifest(
            {"name": "a", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"},
            {"name": "b", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"},
            {
                "name": "c",
                "class": "wurzel.steps.splitter.SimpleSplitterStep",
                "dependsOn": ["a", "b"],
            },
        )
        graph = ManifestBuilder(manifest).build_step_graph()
        c_step = graph["c"]
        assert graph["a"] in c_step.required_steps
        assert graph["b"] in c_step.required_steps

    def test_bad_class_raises(self):
        manifest = _manifest({"name": "s", "class": "nonexistent.module.Step"})
        with pytest.raises(ImportError):
            ManifestBuilder(manifest).build_step_graph()


class TestFindTerminalSteps:
    def test_single_step_is_terminal(self):
        manifest = _manifest({"name": "src", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"})
        builder = ManifestBuilder(manifest)
        graph = builder.build_step_graph()
        terminals = builder.find_terminal_steps(graph)
        assert len(terminals) == 1
        assert graph["src"] in terminals

    def test_terminal_is_last_in_chain(self):
        manifest = _manifest(
            {"name": "src", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"},
            {
                "name": "split",
                "class": "wurzel.steps.splitter.SimpleSplitterStep",
                "dependsOn": ["src"],
            },
        )
        builder = ManifestBuilder(manifest)
        graph = builder.build_step_graph()
        terminals = builder.find_terminal_steps(graph)
        assert graph["split"] in terminals
        assert graph["src"] not in terminals

    def test_two_independent_branches_both_terminal(self):
        manifest = _manifest(
            {"name": "a", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"},
            {"name": "b", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"},
        )
        builder = ManifestBuilder(manifest)
        graph = builder.build_step_graph()
        terminals = builder.find_terminal_steps(graph)
        assert len(terminals) == 2
