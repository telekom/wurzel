# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


from wurzel.manifest.models import (
    Metadata,
    MiddlewareSpec,
    PipelineManifest,
    PipelineSpec,
    StepSpec,
)
from wurzel.manifest.validator import ManifestValidator


def _make_manifest(steps: list[dict], middlewares: list[dict] | None = None) -> PipelineManifest:
    return PipelineManifest(
        metadata=Metadata(name="test"),
        spec=PipelineSpec(
            backend="dvc",
            middlewares=[MiddlewareSpec(**m) for m in (middlewares or [])],
            steps=[StepSpec.model_validate(s) for s in steps],
        ),
    )


class TestValidateStepRefs:
    def test_valid_refs_returns_no_errors(self):
        manifest = _make_manifest(
            [
                {"name": "a", "class": "x.A"},
                {"name": "b", "class": "x.B", "dependsOn": ["a"]},
            ]
        )
        assert ManifestValidator(manifest).validate_step_refs() == []

    def test_undefined_ref_returns_error(self):
        manifest = _make_manifest(
            [
                {"name": "b", "class": "x.B", "dependsOn": ["nonexistent"]},
            ]
        )
        errors = ManifestValidator(manifest).validate_step_refs()
        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_multiple_undefined_refs(self):
        manifest = _make_manifest(
            [
                {"name": "b", "class": "x.B", "dependsOn": ["x", "y"]},
            ]
        )
        errors = ManifestValidator(manifest).validate_step_refs()
        assert len(errors) == 2

    def test_fan_in_valid_refs(self):
        manifest = _make_manifest(
            [
                {"name": "a", "class": "x.A"},
                {"name": "b", "class": "x.B"},
                {"name": "c", "class": "x.C", "dependsOn": ["a", "b"]},
            ]
        )
        assert ManifestValidator(manifest).validate_step_refs() == []


class TestValidateNoCycles:
    def test_linear_chain_no_cycle(self):
        manifest = _make_manifest(
            [
                {"name": "a", "class": "x.A"},
                {"name": "b", "class": "x.B", "dependsOn": ["a"]},
                {"name": "c", "class": "x.C", "dependsOn": ["b"]},
            ]
        )
        assert ManifestValidator(manifest).validate_no_cycles() == []

    def test_direct_cycle_detected(self):
        manifest = _make_manifest(
            [
                {"name": "a", "class": "x.A", "dependsOn": ["b"]},
                {"name": "b", "class": "x.B", "dependsOn": ["a"]},
            ]
        )
        errors = ManifestValidator(manifest).validate_no_cycles()
        assert len(errors) >= 1

    def test_self_reference_detected(self):
        manifest = _make_manifest(
            [
                {"name": "a", "class": "x.A", "dependsOn": ["a"]},
            ]
        )
        errors = ManifestValidator(manifest).validate_no_cycles()
        assert len(errors) >= 1

    def test_transitive_cycle_detected(self):
        manifest = _make_manifest(
            [
                {"name": "a", "class": "x.A", "dependsOn": ["c"]},
                {"name": "b", "class": "x.B", "dependsOn": ["a"]},
                {"name": "c", "class": "x.C", "dependsOn": ["b"]},
            ]
        )
        errors = ManifestValidator(manifest).validate_no_cycles()
        assert len(errors) >= 1

    def test_fan_in_no_cycle(self):
        manifest = _make_manifest(
            [
                {"name": "a", "class": "x.A"},
                {"name": "b", "class": "x.B"},
                {"name": "c", "class": "x.C", "dependsOn": ["a", "b"]},
            ]
        )
        assert ManifestValidator(manifest).validate_no_cycles() == []


class TestValidateClassPaths:
    def test_importable_class_no_error(self):
        manifest = _make_manifest(
            [
                {"name": "s", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"},
            ]
        )
        errors = ManifestValidator(manifest).validate_class_paths()
        assert errors == []

    def test_nonexistent_module_returns_error(self):
        manifest = _make_manifest(
            [
                {"name": "s", "class": "nonexistent.module.Step"},
            ]
        )
        errors = ManifestValidator(manifest).validate_class_paths()
        assert len(errors) == 1
        assert "nonexistent.module.Step" in errors[0]

    def test_nonexistent_class_in_valid_module_returns_error(self):
        manifest = _make_manifest(
            [
                {"name": "s", "class": "wurzel.steps.manual_markdown.NonExistentStep"},
            ]
        )
        errors = ManifestValidator(manifest).validate_class_paths()
        assert len(errors) == 1


class TestValidateMiddlewareNames:
    def test_registered_middleware_no_error(self):
        manifest = _make_manifest(
            steps=[{"name": "s", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"}],
            middlewares=[{"name": "prometheus"}],
        )
        errors = ManifestValidator(manifest).validate_middleware_names()
        assert errors == []

    def test_unregistered_middleware_returns_error(self):
        manifest = _make_manifest(
            steps=[{"name": "s", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"}],
            middlewares=[{"name": "nonexistent_middleware"}],
        )
        errors = ManifestValidator(manifest).validate_middleware_names()
        assert len(errors) == 1
        assert "nonexistent_middleware" in errors[0]

    def test_empty_middlewares_no_error(self):
        manifest = _make_manifest(
            steps=[{"name": "s", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"}],
        )
        assert ManifestValidator(manifest).validate_middleware_names() == []


class TestValidateNoCyclesWithUndefinedRefs:
    def test_undefined_ref_in_depends_on_skipped_in_cycle_check(self):
        """A dependsOn referencing a nonexistent step is skipped (line 47 continue),
        not treated as a cycle. validate_step_refs catches the bad ref separately.
        """
        manifest = _make_manifest(
            [
                {"name": "a", "class": "x.A", "dependsOn": ["nonexistent"]},
            ]
        )
        cycle_errors = ManifestValidator(manifest).validate_no_cycles()
        assert cycle_errors == []
        ref_errors = ManifestValidator(manifest).validate_step_refs()
        assert len(ref_errors) == 1


class TestValidateAll:
    def test_valid_manifest_returns_no_errors(self):
        manifest = _make_manifest(
            [
                {"name": "src", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"},
                {"name": "spl", "class": "wurzel.steps.splitter.SimpleSplitterStep", "dependsOn": ["src"]},
            ]
        )
        errors = ManifestValidator(manifest).validate_all()
        assert errors == []

    def test_multiple_errors_aggregated(self):
        manifest = _make_manifest(
            [
                {"name": "a", "class": "no.such.Module", "dependsOn": ["ghost"]},
            ]
        )
        errors = ManifestValidator(manifest).validate_all()
        # both a ref error and an import error should be present
        assert len(errors) >= 2
