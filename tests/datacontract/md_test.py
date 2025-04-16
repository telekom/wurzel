# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

import wurzel
from wurzel.step import MarkdownDataContract


@pytest.mark.parametrize(
    "md,url,bread",
    [
        ("\n---\n\nurl:myurl\n\n---\nText", "myurl", ""),
        ("\n---\n\n   url:myurl\n\n---\nText", "myurl", ""),
        ("\n---\n\n\t url:myurl\n\n---\nText", "myurl", ""),
        ("\n---\n\nurl:myurl\n\ntopics:bread\n\n---\nText", "myurl", "bread"),
        (
            "\n---\n\nurl:myurl\n\ntopics:bread,butter\n\n---\nText",
            "myurl",
            "bread,butter",
        ),
        ("\n---\n\n\ntopics:bread,butter\n\n---\nText", "", "bread,butter"),
    ],
)
def test_manual_step_md_parsing(tmp_path, md, url, bread):
    f = tmp_path / "file.md"
    f.write_text(md)
    s = MarkdownDataContract.from_file(f, url_prefix="SPACE/")
    if url:
        assert s.url == url
    else:
        assert s.url.startswith("SPACE/")
        assert s.url.endswith("file.md")
    assert s.keywords == (bread or "file")
    assert s.md == "Text"


class MDCChild(MarkdownDataContract):
    pass


class SameDefPyd(wurzel.datacontract.PydanticModel):
    md: str
    keywords: str
    url: str


@pytest.mark.parametrize(
    ["a", "b", "outcome"],
    [
        pytest.param(
            MarkdownDataContract(md="md", keywords="key words", url="u r l"),
            {"md": "md", "keywords": "key words", "url": "u r l"},
            True,
            id="mdc==dict",
        ),
        pytest.param(
            MarkdownDataContract(md="md", keywords="key words", url="u r l"),
            MarkdownDataContract(md="md", keywords="key words", url="u r l"),
            True,
            id="mdc==mdc",
        ),
        pytest.param(
            MarkdownDataContract(md="md", keywords="key words", url="u r l"),
            MDCChild(md="md", keywords="key words", url="u r l"),
            True,
            id="mdc==mdcChild",
        ),
        pytest.param(
            MarkdownDataContract(md="md", keywords="key words", url="u r l"),
            SameDefPyd(md="md", keywords="key words", url="u r l"),
            True,
            id="mdc==Compatible",
        ),
        pytest.param(
            MarkdownDataContract(md="mds", keywords="key words", url="u r l"),
            {"md": "md", "keywords": "key words", "url": "u r l"},
            False,
            id="mdc!=dict",
        ),
        pytest.param(
            MarkdownDataContract(md="md", keywords="key words", url="u r l"),
            MarkdownDataContract(md="mds", keywords="key words", url="u r l"),
            False,
            id="mdc!=mdc",
        ),
        pytest.param(
            MarkdownDataContract(md="mds", keywords="key words", url="u r l"),
            MDCChild(md="md", keywords="key words", url="u r l"),
            False,
            id="mdc!=mdcChild",
        ),
        pytest.param(
            MarkdownDataContract(md="md", keywords="key words", url="u r l"),
            SameDefPyd(md="mds", keywords="key words", url="u r l"),
            False,
            id="mdc!=Compatible",
        ),
    ],
)
def test_equality_and_hash(a, b, outcome):
    obj_equal = a == b
    if isinstance(a, MarkdownDataContract) and isinstance(b, MarkdownDataContract):
        hash_equal = hash(a) == hash(b)
        assert obj_equal == hash_equal
    assert obj_equal == outcome
