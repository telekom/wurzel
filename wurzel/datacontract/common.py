# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import logging
import re
from pathlib import Path
from typing import Any, Callable, Self

import pydantic
import yaml

from .datacontract import PydanticModel

_RE_METADATA = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL | re.MULTILINE)

logger = logging.getLogger(__name__)


class MarkdownDataContract(PydanticModel):
    """A data contract of the input of the EmbeddingStep representing a document in Markdown format.

    The document consists have the Markdown body (document content) and additional metadata (keywords, url).
    """

    md: str
    keywords: str
    url: str  # Url of pydantic is buggy in serialization

    @classmethod
    @pydantic.validate_call
    def from_dict_w_function(cls, doc: dict[str, Any], func: Callable[[str], str]):
        """Create a MarkdownDataContract from a dict and apply a custom func to test."""
        return cls(
            md=func(doc["text"]),
            url=doc["metadata"]["url"],
            keywords=doc["metadata"]["keywords"],
        )

    @classmethod
    def from_file(cls, path: Path, url_prefix: str = "") -> Self:
        """Load MdContract from .md file and parse YAML metadata from header.

        Args:
            path (Path): Path to a Markdown file.

        Returns:
            MarkdownDataContract: The file that was loaded

        """
        # Read MD from file path
        md = path.read_text()

        # Regex to match YAML metadata between --- ... ---
        metadata = {}
        metadata_match = _RE_METADATA.match(md)
        if metadata_match:
            yaml_str, md_body = metadata_match.groups()

            # Parse YAML string
            try:
                metadata = yaml.safe_load(yaml_str)
            except yaml.YAMLError as e:
                logger.error(f"Cannot parse YAML metadata in MarkdownDataContract from {path}: {e}", extra={"path": path, "md": md})

            if not isinstance(metadata, dict):
                logger.error(
                    f"YAML metadata must be a dictionary in MarkdownDataContract from {path}", extra={"path": path, "metadata": metadata}
                )
                metadata = {}  # Overwrite invalid metadata
        else:
            # No YAML metadata, whole markdown string as body
            md_body = md
            logger.warning(f"MarkdownDataContract has no YAML metadata: {path}", extra={"path": path, "md": md})

        return MarkdownDataContract(
            md=md_body,
            # Extract metadata fields or use default value
            url=metadata.get("url", url_prefix + str(path.absolute())),
            keywords=metadata.get("topics", path.name.split(".")[0]),
        )
