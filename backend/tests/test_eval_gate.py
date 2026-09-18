"""The CI retrieval gate.

The gate is the only thing standing between a retrieval regression and `main`,
so it is worth testing that it actually fails — a gate that passes on anything
is worse than none, because it reports safety it is not measuring.
"""

import copy

import pytest

from eval.gate import (
    DEFAULT_CONFIG,
    FLOORS,
    check_config_drift,
    check_floors,
    load_result,
    main,
)


@pytest.fixture
def shipped_run() -> dict:
    return load_result(DEFAULT_CONFIG)


class _Settings:
    """The production defaults the gated run must still describe."""

    retrieval_chunks_per_document = 2
    rerank_enabled = True
    graph_prefer_domain_entities = False
    retrieval_top_k = 15
    embedding_model_name = "all-MiniLM-L6-v2"


class TestFloors:
    def test_the_committed_shipped_run_passes(self, shipped_run):
        """The regression guard itself. If this fails, retrieval got worse."""
        assert check_floors(shipped_run) == []

    def test_every_floor_sits_below_the_value_it_was_derived_from(self):
        """A floor at or above its measurement would fail on the day it shipped."""
        for metric, (floor, measured) in FLOORS.items():
            assert floor < measured, metric

    def test_a_metric_below_its_floor_is_caught(self, shipped_run):
        run = copy.deepcopy(shipped_run)
        run["summary"]["answerable"]["passage_recall_at_5"] = 0.50

        breaches = check_floors(run)

        assert [b.metric for b in breaches] == ["passage_recall_at_5"]
        assert "0.5000 < floor 0.6800" in str(breaches[0])

    def test_the_stage_5_baseline_fails_the_shipped_floors(self):
        """The floors are derived from `passage2`, and that choice matters.

        The Stage 5 baseline is a real, measured, once-shipped configuration
        that is 16.7 points worse on passage recall. The roadmap's original
        floors (passage recall >= 0.50) would have passed it silently; these
        do not. This is the "deliberately introduced regression" the stage 6
        exit criterion asks for, using real data rather than a contrived one.
        """
        breaches = check_floors(load_result("baseline"))

        assert {b.metric for b in breaches} == {"passage_recall_at_5", "evidence_in_context"}

    def test_a_metric_exactly_on_its_floor_passes(self, shipped_run):
        run = copy.deepcopy(shipped_run)
        floor, _ = FLOORS["mrr"]
        run["summary"]["answerable"]["mrr"] = floor

        assert check_floors(run) == []


class TestConfigDrift:
    def test_the_shipped_run_matches_the_shipped_settings(self, shipped_run):
        assert check_config_drift(shipped_run, _Settings()) == []

    def test_a_run_from_a_different_configuration_is_caught(self, shipped_run):
        """Gating a config production no longer runs is a silent failure."""
        run = copy.deepcopy(shipped_run)
        run["settings"]["chunks_per_document"] = 1

        breaches = check_config_drift(run, _Settings())

        assert [b.metric for b in breaches] == ["chunks_per_document"]
        assert "run has 1, code ships 2" in str(breaches[0])

    def test_promoting_the_graph_flag_without_re_measuring_is_caught(self, shipped_run):
        """The flag Stage 5 kept off. Turning it on invalidates these numbers."""

        class Promoted(_Settings):
            graph_prefer_domain_entities = True

        breaches = check_config_drift(shipped_run, Promoted())

        assert [b.metric for b in breaches] == ["graph_prefer_domain_entities"]

    def test_a_key_the_run_predates_is_skipped_rather_than_failed(self, shipped_run):
        run = copy.deepcopy(shipped_run)
        del run["settings"]["chunks_per_document"]

        assert check_config_drift(run, _Settings()) == []


class TestCli:
    def test_exit_code_is_zero_for_the_shipped_config(self, capsys):
        assert main([]) == 0
        assert "All floors met" in capsys.readouterr().out

    def test_exit_code_is_one_when_a_floor_is_breached(self, capsys):
        assert main(["--config", "baseline"]) == 1
        assert "check(s) failed" in capsys.readouterr().out

    def test_an_unknown_config_names_the_command_that_produces_it(self):
        with pytest.raises(FileNotFoundError, match="python -m eval.run retrieval"):
            load_result("no_such_config")
