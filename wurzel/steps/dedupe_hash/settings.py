# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from dotenv import load_dotenv
from pydantic import Field

from wurzel.step.settings import Settings  # falls Settings eine Pydantic-Basisklasse ist

# Lade .env-Datei automatisch
load_dotenv()


class QdrantCompareSettings(Settings):
    """Configuration settings for comparing two Qdrant collections.

    This class defines all environment-configurable parameters required for
    analyzing differences, redundancies, and contradictions between two Qdrant
    collections. It supports integration with Azure and OpenAI for advanced
    deduplication and fuzzy matching. All settings can be loaded from environment
    variables or a .env file, making it suitable for flexible deployment and
    secure configuration management.

    Attributes:
        QDRANT_URL (str): Base URL for Qdrant.
        QDRANT_API_KEY (str): API key for Qdrant access.
        AZURE_ENDPOINT (str): Endpoint for Azure access.
        FUZZY_THRESHOLD (int): Fuzzy match threshold for Qdrant.
        TLSH_MAX_DIFF (int): Maximum TLSH difference for deduplication.
        OPAI_API_KEY (str): OpenAI API key for deduplication.
        GPT_MODEL (str): OpenAI model to use for deduplication.
        QDRANT_COLLECTION_PREFIX (str): Prefix for Qdrant collection names to extract versions.

    """

    QDRANT_URL: str = Field(
        "",
        description="Base URL for Qdrant.",
    )
    QDRANT_API_KEY: str = Field(
        "",
        description="API key for Qdrant access.",
    )

    AZURE_ENDPOINT: str = Field("", description="ENDPOINT for AZURE acces.")

    FUZZY_THRESHOLD: int = Field(
        99,
        description="Fuzzy match threshold for Qdrant.",
    )
    TLSH_MAX_DIFF: int = Field(
        1,
        description="Maximum TLSH difference for deduplication.",
    )
    OPAI_API_KEY: str = Field(
        "",
        description="OpenAI API key for deduplication.",
    )
    GPT_MODEL: str = Field(
        "GPT4-CH",
        description="OpenAI model to use for deduplication.",
    )
    QDRANT_COLLECTION_PREFIX: str = Field(
        "",
        description="Prefix for Qdrant collection names to extract versions.",
    )
    IDENTICAL_WARNING_THRESHOLD: float = Field(0.8, description="Warn if identical documents are below this fraction")  # z.B. 0.9 für 90%

    class Config:
        """Compares two Qdrant collections and analyzes differences, redundancies, and contradictions."""

        env_prefix = "QDRANTCOMPARESTEP__"
        env_file = ".env"
