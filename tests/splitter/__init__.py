# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import importlib

from wurzel.utils import HAS_SPACY, HAS_TIKTOKEN, HAS_TRANSFORMERS

# Helpers for skip conditions
spacy_missing = not HAS_SPACY
tokenizer_missing = not HAS_TIKTOKEN and not HAS_TRANSFORMERS
spacy_default_model_name = "de_core_news_sm"
spacy_multilingual_model_name = "xx_ent_wiki_sm"
wtpsplit_missing = importlib.util.find_spec("wtpsplit") is None
