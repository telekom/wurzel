# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


from wurzel.cli.cmd_generate import main


class DummyBackend:
    def generate_artifact(self, step):
        return "ok"


class DummyStep:
    def traverse(self):
        return []


def test_cmd_generate_runs():
    res = main(DummyStep(), DummyBackend)
    assert res == "ok"
