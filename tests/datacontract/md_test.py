# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

import wurzel
from wurzel.core import MarkdownDataContract


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

    # check metadata field
    assert s.metadata is None


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


def test_topics_deprecation_warning(tmp_path):
    with pytest.warns(DeprecationWarning, match="`topics` metadata field is deprecated "):
        f = tmp_path / "file.md"
        f.write_text("---\ntopics: foo\n---\n# Some title\n\nMore text.")
        s = MarkdownDataContract.from_file(f, url_prefix="SPACE/")
        assert s.md.startswith("# Some title")


def test_markdown_data_contract_metrics():
    doc = MarkdownDataContract(md="Hello\nWorld", keywords="bread, butter, ,", url="u")
    metrics = doc.metrics()

    assert metrics["md_char_len"] == float(len(doc.md))
    assert metrics["md_line_count"] == float(len(doc.md.splitlines()))
    assert metrics["keywords_count"] == 2.0


def test_markdown_data_contract_metrics_aggregated():
    doc_a = MarkdownDataContract(md="abcd", keywords="a,b", url="u")
    doc_b = MarkdownDataContract(md="xyz", keywords="c", url="u")

    metrics = MarkdownDataContract.get_metrics([doc_a, doc_b])

    assert metrics["md_char_len"] == float(len(doc_a.md) + len(doc_b.md))
    assert metrics["md_line_count"] == float(len(doc_a.md.splitlines()) + len(doc_b.md.splitlines()))
    assert metrics["keywords_count"] == 3.0


def test_metadata_field_metadata(tmp_path):
    md = """---
keywords: "k1"
url: foo/bar
metadata:
 foo: bar
 bar: 123
---
# Title

Text.
 """
    f = tmp_path / "file.md"
    f.write_text(md)
    s = MarkdownDataContract.from_file(f)

    assert "# Title" in s.md
    assert s.metadata is not None
    assert s.metadata["foo"] == "bar"
    assert s.metadata["bar"] == 123
    assert s.url == "foo/bar"

    assert s.__hash__() == 21317556317919954558699657768736304700342060298586059611903002870732316103488, "Invalid hash"

    # save and load again
    f2 = tmp_path / "file2.json"

    MarkdownDataContract.save_to_path(f2, s)

    s2 = MarkdownDataContract.load_from_path(f2, MarkdownDataContract)

    assert s.__hash__() == s2.__hash__(), "Invalid hash after write/load file"


def test_utf8_encoding(tmp_path):
    """Test that UTF-8 encoded files are read correctly, especially on Windows."""
    f = tmp_path / "file.md"
    # Write UTF-8 content explicitly
    utf8_content = "---\nkeywords: test,unicode\n---\n# UTF-8 Test\nContent with émojis 🎉 and spëcial çharacters."
    f.write_text(utf8_content, encoding="utf-8")

    s = MarkdownDataContract.from_file(f, url_prefix="SPACE/")

    # Verify UTF-8 characters are preserved
    assert "🎉" in s.md
    assert "émojis" in s.md
    assert "spëcial" in s.md
    assert "çharacters" in s.md
    assert s.keywords == "test,unicode"
