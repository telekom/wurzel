from pathlib import Path

import yaml

from wurzel.step.typed_step import TypedStep


class Backend:
    """Abstract class to specify the Backend."""

    def generate_dict(self, step: TypedStep) -> dict:
        """Generate the dict."""
        raise NotImplementedError()

    def generate_yaml(self, step: TypedStep) -> str:
        """Generate the yaml."""
        raise NotImplementedError()

    @classmethod
    def save_yaml(cls, yml: str, file: Path):
        """Saves given yml string int file."""
        with open(file, "w", encoding="utf-8") as f:
            yaml.dump(yml, f)
