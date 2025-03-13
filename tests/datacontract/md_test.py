# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel import MarkdownDataContract


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
