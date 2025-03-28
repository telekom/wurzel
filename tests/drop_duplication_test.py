# SPDX-FileCopyrightmd: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import os

from wurzel.datacontract import MarkdownDataContract
from wurzel.steps.duplication import DropDuplicationStep


def test_full_duplications():
    "10 exact equal documents"
    test_data = [
        MarkdownDataContract(
            md="##Hello World", keywords="dummy", url="https:example.com/hello"
        )
        for _ in range(10)
    ]

    step = DropDuplicationStep()
    result = step.run(test_data)
    assert len(result) == 1
    assert isinstance(result[0], MarkdownDataContract)


def test_no_duplications():
    "10 exact equal documents"
    test_data = [
        MarkdownDataContract(
            md=f"##Hello World {i}", keywords="dummy", url="https:example.com/hello"
        )
        for i in range(10)
    ]

    step = DropDuplicationStep()
    result = step.run(test_data)
    assert len(result) == 10
    assert isinstance(result[0], MarkdownDataContract)


def test_subset_duplications():
    "10 exact equal documents"
    os.environ["DROP_BY_FIELDS"] = '["url"]'  # TODO env fixutire
    test_data = [
        MarkdownDataContract(
            md=f"##Hello World {i}", keywords="dummy", url="https:example.com/hello"
        )
        for i in range(10)
    ]

    step = DropDuplicationStep()
    result = step.run(test_data)
    assert len(result) == 1
    assert isinstance(result[0], MarkdownDataContract)


def test_subset_md_equal_but_url_diff_duplications():
    "10 exact equal documents"
    os.environ["DROP_BY_FIELDS"] = '["*"]'
    test_data = [
        MarkdownDataContract(
            md="##Hello World", keywords="dummy", url=f"https:example.com/hello{i}"
        )
        for i in range(10)
    ]

    step = DropDuplicationStep()
    result = step.run(test_data)
    assert len(result) == 10
    assert isinstance(result[0], MarkdownDataContract)


def test_all_duplications():
    "10 exact equal documents"
    os.environ["DROP_BY_FIELDS"] = '["*"]'
    test_data = [
        MarkdownDataContract(
            md="##Hello World", keywords="dummy", url="https:example.com/hello"
        )
        for i in range(10)
    ]

    step = DropDuplicationStep()
    result = step.run(test_data)
    assert len(result) == 1
    assert isinstance(result[0], MarkdownDataContract)
