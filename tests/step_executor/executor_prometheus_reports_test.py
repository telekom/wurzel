# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import logging

from wurzel.datacontract.common import MarkdownDataContract
from wurzel.step import NoSettings, TypedStep
from wurzel.step_executor import PrometheusStepExecutor

logger = logging.getLogger(__name__)


class TstAStep(TypedStep[NoSettings, None, MarkdownDataContract]):
    def run(self, inputs: None) -> MarkdownDataContract:
        logger.info("A: just an info")
        logger.warning("A: warning")

        return MarkdownDataContract(md="A", keywords="A", url="A")


class TstBStep(TypedStep[NoSettings, MarkdownDataContract, list[MarkdownDataContract]]):
    def run(self, inputs: MarkdownDataContract) -> list[MarkdownDataContract]:
        for _ in range(10):
            logger.error("B: error")
        return [inputs, inputs]


class TstCStep(TypedStep[NoSettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    def run(self, inputs: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        return inputs


class TstDStep(TypedStep[NoSettings, list[MarkdownDataContract], MarkdownDataContract]):
    def run(self, inputs: list[MarkdownDataContract]) -> MarkdownDataContract:
        for _ in range(4):
            logger.warning("D: warning")
        for _ in range(6):
            logger.error("B: error")

        return inputs[0]


def test_multi_step_pipeline_with_history_labels_and_log_counter(tmp_path, env):
    # multiple tests in one function to ensure isolation for ENV var changes

    with PrometheusStepExecutor() as ex:
        # 1) basic test without pipeline ID
        out_a = tmp_path / "out_a"
        out_b = tmp_path / "out_b"
        out_c = tmp_path / "out_c"
        out_d = tmp_path / "out_d"

        ex.execute_step(TstAStep, None, out_a)
        ex.execute_step(TstBStep, (out_a,), out_b)
        ex.execute_step(TstCStep, (out_b,), out_c)
        ex.execute_step(TstDStep, (out_c,), out_d)

        assert len(ex.counter_results.collect()[0].samples) == 8

        # Check labels
        for sample in ex.counter_results.collect()[0].samples:
            assert sample.labels["history_first_step"] == "TstA"

        assert ex.counter_results.collect()[0].samples[0].labels["history_last_step"] == "TstA"
        assert ex.counter_results.collect()[0].samples[-1].labels["history_last_step"] == "TstD"

        # Check log counter
        assert ex.counter_log_error_counts.collect()[0].samples[2].value == 10
        assert ex.counter_log_error_counts.collect()[0].samples[-2].value == 6
        assert ex.counter_log_warning_counts.collect()[0].samples[0].value == 1

        # clear counter
        ex.counter_results.clear()

        # 2) pipeline ID from single env var
        env.set("WZ_PIPELINE_ID_ENV_VARIABLES", "WZ_PIPELINE_ID")
        env.set("WZ_PIPELINE_ID", "my-pipeline-123")

        out_a = tmp_path / "out_a"

        ex.execute_step(TstAStep, None, out_a)

        # Check labels
        for sample in ex.counter_results.collect()[0].samples:
            assert sample.labels["pipeline_id"] == "my-pipeline-123"

        # clear counter
        ex.counter_results.clear()

        # 3) pipeline ID from multiple env vars
        env.set("WZ_PIPELINE_ID_ENV_VARIABLES", "WZ_TENANT,WZ_PIPELINE_ID")
        env.set("WZ_TENANT", "abc")
        env.set("WZ_PIPELINE_ID", "my-pipeline-123")

        out_a = tmp_path / "out_a"

        ex.execute_step(TstAStep, None, out_a)

        # Check labels
        for sample in ex.counter_results.collect()[0].samples:
            assert sample.labels["pipeline_id"] == "abc__my-pipeline-123"

        # clear counter
        ex.counter_results.clear()
