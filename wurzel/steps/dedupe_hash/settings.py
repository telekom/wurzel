from wurzel.step.settings import Settings
"""
class QdrantCompareSettings(Settings):
    QDRANT_URL: str = "https://qdrant.intra.oneai.yo-digital.com"
    API_KEY: str = "RSFR0bjRIQ1FUcT"
    FUZZY_THRESHOLD: int = 99
    TLSH_MAX_DIFF: int = 1
    OPAI_API_KEY: str = "5f65edd5152a475dac99ea8f555dc3a9"
    GPT_MODEL: str = "GPT4-CH"
    prefix: str = "germany_v"

    # GPT_MODEL kannst du optional auch noch angeben, falls du es brauchst:
    # GPT_MODEL: str = "GPT4-CH"
"""


# step/settings.py
import os
from dotenv import load_dotenv
from wurzel.step.settings import Settings  # falls Settings eine Pydantic-Basisklasse ist

# Lade .env-Datei automatisch
load_dotenv()

class QdrantCompareSettings(Settings):
    QDRANT_URL: str = os.getenv("QDRANT_URL", "https://qdrant.intra.oneai.yo-digital.com")
    API_KEY: str = os.getenv("QDRANT_API_KEY", "XXX")
    FUZZY_THRESHOLD: int = int(os.getenv("FUZZY_THRESHOLD", 99))
    TLSH_MAX_DIFF: int = int(os.getenv("TLSH_MAX_DIFF", 1))
    OPAI_API_KEY: str = os.getenv("OPAI_API_KEY", "XXX")
    GPT_MODEL: str = os.getenv("GPT_MODEL", "GPT4-CH")
    prefix: str = os.getenv("PREFIX", "germany_v")
