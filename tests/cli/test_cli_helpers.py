# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import ast

from wurzel.cli._main import _check_if_typed_step, _process_python_file


def test_check_if_typed_step():
    # Test with a class that inherits from TypedStep
    code = """
class MyStep(TypedStep):
    pass
"""
    tree = ast.parse(code)
    class_node = tree.body[0]
    assert _check_if_typed_step(class_node) is True

    # Test with a class that doesn't inherit from TypedStep
    code2 = """
class MyOtherClass:
    pass
"""
    tree2 = ast.parse(code2)
    class_node2 = tree2.body[0]
    assert _check_if_typed_step(class_node2) is False


def test_process_python_file(tmp_path):
    # Create a test Python file with a TypedStep
    test_file = tmp_path / "test_step.py"
    test_file.write_text("""
from wurzel.step.typed_step import TypedStep

class TestStep(TypedStep):
    pass

class NotAStep:
    pass
""")

    hints = []
    _process_python_file(test_file, tmp_path, "test", "test", hints)

    # Should find TestStep but not NotAStep
    assert len(hints) == 1
    assert "TestStep" in hints[0]


def test_process_python_file_no_typedstep(tmp_path):
    # Create a test Python file without TypedStep
    test_file = tmp_path / "no_step.py"
    test_file.write_text("""
class RegularClass:
    pass
""")

    hints = []
    _process_python_file(test_file, tmp_path, "test", "test", hints)

    # Should find nothing
    assert len(hints) == 0
