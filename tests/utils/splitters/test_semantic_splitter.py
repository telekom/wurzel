# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import re

from wurzel.datacontract import MarkdownDataContract
from wurzel.steps.splitter import SimpleSplitterStep

SAMPLE_MD_ESCAPED = (
    "# Gyakran ism\u00e9telt k\u00e9rd\u00e9sek\n"
    "## Mi a teend\u0151m, ha elfelejtettem az online jelszavam?\n"
    "Oldalunkra k\u00e9tf\u00e9le m\u00f3don jelentkezhetsz be:\\\\mn Oldalunkra"
)
SAMPLE_KEYWORDS_ESCAPED = r"TV Fehlerbehebung"
SAMPLE_URL = (
    "http://telekom.hu/lakossagi/ugyintezes/gyakori-kerdesek/7/mi_a_teendom__ha_elfelejtettem_az_online_belepeshez_szukseges_jelszavam"
)
SINGLE_NEWLINE_RE = re.compile(r"(?<!\n)\n(?!\n)")


def decode_escaped(s: str) -> str:
    """Decode the JSON-style unicode escape sequences in the sample string."""
    return s.encode("utf-8").decode("unicode_escape")


def make_doc():
    md = decode_escaped(SAMPLE_MD_ESCAPED)
    keywords = decode_escaped(SAMPLE_KEYWORDS_ESCAPED)
    return MarkdownDataContract(md=md, url=SAMPLE_URL, keywords=keywords)


def test_splitter_preserves_newlines():
    """Test that SimpleSplitterStep does not introduce extra newlines in the output."""
    step = SimpleSplitterStep()
    doc = make_doc()
    output_docs = step.run([doc])
    joined_text = "\n".join(doc.md for doc in output_docs)
    original_newline_count = doc.md.count("\n")
    new_newline_count = joined_text.count("\n")
    # Assert: No double newlines were introduced
    assert "\n\n" not in joined_text, "Unexpected multiple newlines found in output"

    assert abs(new_newline_count - original_newline_count) <= 1, (
        f"Expected newline count close to {original_newline_count}, but got {new_newline_count}"
    )
