
# step/settings.py
import os
from dotenv import load_dotenv
from wurzel.step.settings import Settings  # falls Settings eine Pydantic-Basisklasse ist
from pydantic import Field

# Lade .env-Datei automatisch
load_dotenv()


class QdrantCompareSettings(Settings):
        QDRANT_URL: str = Field(
            "",
            description="Base URL for Qdrant.",
        )
        QDRANT_API_KEY: str = Field(
            "",
            description="API key for Qdrant access.",
        )
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

        class Config:
            env_prefix = "QDRANTCOMPARESTEP__"
            env_file = ".env"

