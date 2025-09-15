# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

import wurzel
from wurzel.step import MarkdownDataContract


@pytest.mark.parametrize(
    "md,url,bread",
    [
        ("---\n\nurl: myurl\n---\nText", "myurl", ""),
        ("---\n\n   url: myurl\n---\nText", "myurl", ""),
        ("---\n\n\t url: myurl\n---\nText", "", ""),  # invalid YAML, ignore metadata
        ("---\nurl: myurl\n---\nText", "myurl", ""),
        ("---\n\nurl: myurl\n\nkeywords: bread\n---\nText", "myurl", "bread"),
        (
            "---\n\nurl: myurl\n\nkeywords: bread,butter\n---\nText",
            "myurl",
            "bread,butter",
        ),
        ("---\n\n\nkeywords: bread,butter\n---\nText", "", "bread,butter"),
        (
            "---\n\n\nkeywords: bread,butter\n\n---\nText\nurl:url_body",
            "",
            "bread,butter",
        ),
        (
            "---\n\n\nkeywords: bread,butter\nurl: url_header\n---\nText",
            "url_header",
            "bread,butter",
        ),
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

    if "url:url_body" in md:
        assert s.md == "Text\nurl:url_body"
    else:
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


def test_table_not_metadata(tmp_path):
    md = """some text

| no | header |
| --- | --- |
| but a | table |

some more text

| no | header |
| --- | --- |
| but a | table |"""

    f = tmp_path / "file.md"
    f.write_text(md)
    s = MarkdownDataContract.from_file(f, url_prefix="SPACE/")

    assert s.md == md
    assert s.url.startswith("SPACE/")
    assert s.url.endswith("file.md")


@pytest.mark.parametrize(
    "header_md,body_md",
    [
        (
            """---
fo_ : ",
-
-
#
---
""",
            """# title
some text

some more text

| no | header |
| --- | --- |
| but a | table |""",
        ),  # YAML is invalid syntax
        (
            """---
- foo
- bar
---
""",
            """# title
some text

some more text

| no | header |
| --- | --- |
| but a | table |""",
        ),  # YAML is a list not a dictionary
    ],
)
def test_metadata_invalid_yaml_ignore_metadata(tmp_path, header_md, body_md):
    f = tmp_path / "file.md"
    f.write_text(header_md + "\n" + body_md)
    s = MarkdownDataContract.from_file(f, url_prefix="SPACE/")

    assert s.md == body_md
    assert s.url.startswith("SPACE/")
    assert s.url.endswith("file.md")
