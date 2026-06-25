"""Tests for the ranking module (src/ranking.py)."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.ranking import (
    Leaderboard,
    LeaderboardEntry,
    RankingSystem,
    RunData,
    SVGScore,
)
from src.svg_judge import Judgment


# -- Judgment tests --


class TestJudgment:
    def test_creation_with_scores_dict(self):
        scores = {"creativity": 0.9, "aesthetics": 0.8, "complexity": 0.7}
        judgment = Judgment(
            svg_id="svg-001",
            svg_model_name="model_a",
            judged_by="human-1",
            scores=scores,
        )
        assert judgment.svg_id == "svg-001"
        assert judgment.svg_model_name == "model_a"
        assert judgment.judged_by == "human-1"
        assert judgment.scores == scores

    def test_creation_with_minimal_fields(self):
        judgment = Judgment(
            svg_id="svg-001",
            svg_model_name="model_a",
            judged_by="human-1",
        )
        assert judgment.svg_id == "svg-001"
        assert judgment.scores == {}


# -- SVGScore tests --


class TestSVGScore:
    def test_creation(self):
        svg_score = SVGScore(
            svg_id="svg-001",
            model_name="model_a",
            total_score=1.43,
            judgment_count=2,
            scores={"creativity": 0.9, "aesthetics": 0.8, "complexity": 0.7},
        )
        assert svg_score.svg_id == "svg-001"
        assert svg_score.model_name == "model_a"
        assert svg_score.total_score == 1.43
        assert svg_score.judgment_count == 2

    def test_default_scores_dict(self):
        svg_score = SVGScore(
            svg_id="svg-001",
            model_name="model_a",
        )
        assert svg_score.scores == {}

    def test_get_score_existing(self):
        svg_score = SVGScore(
            svg_id="svg-001",
            model_name="model_a",
            scores={"creativity": 0.9, "dancing": 9.5},
        )
        assert svg_score.get_score("creativity") == 0.9
        assert svg_score.get_score("dancing") == 9.5

    def test_get_score_missing(self):
        svg_score = SVGScore(
            svg_id="svg-001",
            model_name="model_a",
            scores={"creativity": 0.9},
        )
        assert svg_score.get_score("nonexistent") == 0.0


# -- LeaderboardEntry tests --


class TestLeaderboardEntry:
    def test_creation(self):
        entry = LeaderboardEntry(
            rank=1,
            svg_id="svg-001",
            model_name="model_a",
            total_score=0.85,
            judgment_count=3,
        )
        assert entry.rank == 1
        assert entry.svg_id == "svg-001"
        assert entry.model_name == "model_a"
        assert entry.total_score == 0.85
        assert entry.judgment_count == 3

    def test_from_svg_score(self):
        svg_score = SVGScore(
            svg_id="svg-001",
            model_name="model_a",
            total_score=0.85,
            judgment_count=3,
            scores={"creativity": 0.9, "aesthetics": 0.8},
        )
        entry = LeaderboardEntry.from_svg_score(svg_score, rank=1, svg_files=["file1.svg"])
        assert entry.rank == 1
        assert entry.svg_id == "svg-001"
        assert entry.model_name == "model_a"
        assert entry.total_score == 0.85
        assert entry.judgment_count == 3
        assert entry.svg_files == ["file1.svg"]
        assert entry.scores == {"creativity": 0.9, "aesthetics": 0.8}

    def test_from_svg_score_no_svg_files(self):
        svg_score = SVGScore(
            svg_id="svg-002",
            model_name="model_b",
            total_score=0.75,
            judgment_count=2,
            scores={"aesthetics": 0.75},
        )
        entry = LeaderboardEntry.from_svg_score(svg_score, rank=2, svg_files=None)
        assert entry.rank == 2
        assert entry.svg_id == "svg-002"
        assert entry.svg_files == []

    def test_get_score(self):
        entry = LeaderboardEntry(
            rank=1,
            svg_id="svg-001",
            model_name="model_a",
            scores={"creativity": 0.9, "aesthetics": 0.8},
        )
        assert entry.get_score("creativity") == 0.9
        assert entry.get_score("aesthetics") == 0.8
        assert entry.get_score("nonexistent") == 0.0


# -- Leaderboard tests --


class TestLeaderboard:
    def test_creation_with_rankings(self):
        entries = [
            LeaderboardEntry(rank=1, svg_id="svg-001", model_name="model_a", total_score=0.9),
            LeaderboardEntry(rank=2, svg_id="svg-002", model_name="model_b", total_score=0.8),
        ]
        leaderboard = Leaderboard(
            run_id="run-001",
            timestamp="2024-01-01T12:00:00",
            total_judgments=10,
            total_models=2,
            rankings=entries,
            meta={"themes": ["abstract", "landscape"]},
        )
        assert leaderboard.run_id == "run-001"
        assert leaderboard.timestamp == "2024-01-01T12:00:00"
        assert leaderboard.total_judgments == 10
        assert leaderboard.total_models == 2
        assert len(leaderboard.rankings) == 2

    def test_model_dump_returns_dict(self):
        entries = [
            LeaderboardEntry(rank=1, svg_id="svg-001", model_name="model_a", total_score=0.9),
        ]
        leaderboard = Leaderboard(
            run_id="run-001",
            timestamp="2024-01-01T12:00:00",
            total_judgments=5,
            total_models=1,
            rankings=entries,
        )
        dumped = leaderboard.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["run_id"] == "run-001"
        assert dumped["total_judgments"] == 5
        assert len(dumped["rankings"]) == 1


# -- RankingSystem tests --


class TestRankingSystem:
    def test_init_creates_dirs(self, mock_config):
        system = RankingSystem(mock_config)
        assert system.config == mock_config

    def test_init_creates_dirs_with_real_paths(self, temp_output_dir):
        config, tmp_path = temp_output_dir
        system = RankingSystem(config)
        assert config.leaderboards_dir.is_dir()
        assert config.svgs_dir.is_dir()

    def test_aggregate_all_judgments_single(self, mock_config):
        system = RankingSystem(mock_config)
        run_data = Mock()
        run_data.model_list = ["model_a", "model_b"]
        run_data.themes = ["abstract"]
        run_data.judgments = [
            Judgment(
                svg_id="model_a_abstract_pass1",
                svg_model_name="model_a",
                judged_by="human-1",
                scores={"creativity": 0.9, "aesthetics": 0.8, "complexity": 0.7},
            )
        ]
        results = system.aggregate_all_judgments(run_data, run_data.judgments)
        assert "model_a" in results
        svg_score = results["model_a"]
        assert svg_score.svg_id == "model_a"
        assert svg_score.model_name == "model_a"
        assert svg_score.judgment_count == 1
        assert svg_score.scores["creativity"] == 0.9
        assert svg_score.scores["aesthetics"] == 0.8
        assert svg_score.scores["complexity"] == 0.7

    def test_aggregate_all_judgments_multiple_averaging(self, mock_config):
        system = RankingSystem(mock_config)
        run_data = Mock()
        run_data.model_list = ["model_a"]
        run_data.themes = ["abstract"]
        run_data.judgments = [
            Judgment(
                svg_id="model_a_abstract_pass1",
                svg_model_name="model_a",
                judged_by="human-1",
                scores={"creativity": 0.6, "aesthetics": 0.6, "complexity": 0.6},
            ),
            Judgment(
                svg_id="model_a_abstract_pass1",
                svg_model_name="model_a",
                judged_by="human-2",
                scores={"creativity": 1.0, "aesthetics": 1.0, "complexity": 1.0},
            ),
        ]
        results = system.aggregate_all_judgments(run_data, run_data.judgments)
        svg_score = results["model_a"]
        assert svg_score.judgment_count == 2
        assert svg_score.scores["creativity"] == 0.8
        assert svg_score.scores["aesthetics"] == 0.8
        assert svg_score.scores["complexity"] == 0.8

    def test_aggregate_all_judgments_new_format_scores_dict(self, mock_config):
        system = RankingSystem(mock_config)
        run_data = Mock()
        run_data.model_list = ["model_a"]
        run_data.themes = ["abstract"]
        judgment = Judgment(
            svg_id="model_a_abstract_pass1",
            svg_model_name="model_a",
            judged_by="human-1",
            scores={"creativity": 0.9, "aesthetics": 8.0},
        )
        run_data.judgments = [judgment]
        results = system.aggregate_all_judgments(run_data, run_data.judgments)
        svg_score = results["model_a"]
        assert svg_score.scores["creativity"] == 0.9
        assert svg_score.scores["aesthetics"] == 8.0

    def test_calculate_final_ranking_sort_order(self, mock_config):
        system = RankingSystem(mock_config)
        scores = {
            "svg-001": SVGScore(svg_id="svg-001", model_name="model_a", total_score=0.6, scores={"creativity": 0.6}),
            "svg-002": SVGScore(svg_id="svg-002", model_name="model_b", total_score=0.9, scores={"creativity": 0.9}),
            "svg-003": SVGScore(svg_id="svg-003", model_name="model_c", total_score=0.3, scores={"creativity": 0.3}),
        }
        rankings = system.calculate_final_ranking(scores)
        assert len(rankings) == 3
        assert rankings[0].rank == 1
        assert rankings[0].total_score == 0.9
        assert rankings[1].rank == 2
        assert rankings[1].total_score == 0.6
        assert rankings[2].rank == 3
        assert rankings[2].total_score == 0.3

    def test_calculate_final_ranking_assign_ranks(self, mock_config):
        system = RankingSystem(mock_config)
        scores = {
            "svg-001": SVGScore(svg_id="svg-001", model_name="model_a", total_score=1.0, scores={"creativity": 1.0}),
        }
        rankings = system.calculate_final_ranking(scores)
        assert rankings[0].rank == 1
        assert rankings[0].svg_id == "svg-001"

    def test_generate_leaderboard(self, mock_config):
        system = RankingSystem(mock_config)
        run_data = Mock()
        run_data.run_id = "run-001"
        run_data.timestamp = "2024-01-01T12:00:00"
        run_data.model_list = ["model_a", "model_b"]
        run_data.themes = ["abstract"]
        run_data.svgs = []
        run_data.judgments = [
            Judgment(
                svg_id="model_a_abstract_pass1",
                svg_model_name="model_a",
                judged_by="human-1",
                scores={"creativity": 0.9, "aesthetics": 0.8, "complexity": 0.7},
            ),
            Judgment(
                svg_id="model_b_abstract_pass1",
                svg_model_name="model_b",
                judged_by="human-1",
                scores={"creativity": 0.6, "aesthetics": 0.5, "complexity": 0.4},
            ),
        ]
        leaderboard = system.generate_leaderboard(run_data)
        assert isinstance(leaderboard, Leaderboard)
        assert leaderboard.run_id == "run-001"
        assert leaderboard.total_judgments == 2
        assert leaderboard.total_models == 2
        assert len(leaderboard.rankings) == 2
        assert leaderboard.rankings[0].model_name == "model_a"
        assert leaderboard.rankings[0].rank == 1

    def test_save_and_load_leaderboard_round_trip(self, temp_output_dir):
        config, tmp_path = temp_output_dir
        system = RankingSystem(config)
        entries = [
            LeaderboardEntry(rank=1, svg_id="svg-001", model_name="model_a", total_score=0.9),
            LeaderboardEntry(rank=2, svg_id="svg-002", model_name="model_b", total_score=0.8),
        ]
        leaderboard = Leaderboard(
            run_id="run-001",
            timestamp="2024-01-01T12:00:00",
            total_judgments=5,
            total_models=2,
            rankings=entries,
        )
        path = system.save_leaderboard(leaderboard)
        assert Path(path).exists()
        loaded = system.load_leaderboard("run-001")
        assert loaded.run_id == "run-001"
        assert loaded.total_judgments == 5
        assert len(loaded.rankings) == 2
        assert loaded.rankings[0].svg_id == "svg-001"
        assert loaded.rankings[0].rank == 1
        assert loaded.rankings[1].rank == 2

    def test_export_to_csv_header_row(self, mock_config):
        system = RankingSystem(mock_config)
        entries = [
            LeaderboardEntry(rank=1, svg_id="svg-001", model_name="model_a", total_score=0.9, judgment_count=3),
            LeaderboardEntry(rank=2, svg_id="svg-002", model_name="model_b", total_score=0.8, judgment_count=3),
        ]
        leaderboard = Leaderboard(
            run_id="run-001",
            timestamp="2024-01-01T12:00:00",
            total_judgments=6,
            total_models=2,
            rankings=entries,
        )
        csv_path = system.export_to_csv(leaderboard)
        with open(csv_path, "r") as f:
            lines = f.read().strip().split("\n")
        header = lines[0]
        assert "rank" in header
        assert "model" in header
        assert "creativity" in header
        assert "aesthetics" in header
        assert "complexity" in header
        assert "total" in header

    def test_export_to_csv_data_rows(self, mock_config):
        system = RankingSystem(mock_config)
        entries = [
            LeaderboardEntry(rank=1, svg_id="svg-001", model_name="model_a", total_score=0.9, judgment_count=3),
        ]
        leaderboard = Leaderboard(
            run_id="run-001",
            timestamp="2024-01-01T12:00:00",
            total_judgments=3,
            total_models=1,
            rankings=entries,
        )
        csv_path = system.export_to_csv(leaderboard)
        with open(csv_path, "r") as f:
            lines = f.read().strip().split("\n")
        # lines[0] is header, lines[1] is data
        assert len(lines) == 2
        data_row = lines[1].split(",")
        assert data_row[0] == "1"
        assert data_row[1] == "svg-001"

    def test_create_run_id_returns_iso_string(self, mock_config):
        system = RankingSystem(mock_config)
        run_id = system.create_run_id()
        assert isinstance(run_id, str)
        assert len(run_id) > 0
        # ISO format contains 'T' separator for datetime
        assert "T" in run_id

    def test_get_top_models_returns_top_n(self, mock_config):
        system = RankingSystem(mock_config)
        entries = [
            LeaderboardEntry(rank=1, svg_id="svg-001", model_name="model_a", total_score=0.95),
            LeaderboardEntry(rank=2, svg_id="svg-002", model_name="model_b", total_score=0.85),
            LeaderboardEntry(rank=3, svg_id="svg-003", model_name="model_c", total_score=0.75),
        ]
        leaderboard = Leaderboard(
            run_id="run-001",
            timestamp="2024-01-01T12:00:00",
            total_judgments=10,
            total_models=3,
            rankings=entries,
        )
        top3 = system.get_top_models(leaderboard, n=3)
        assert len(top3) == 3
        assert top3[0].svg_id == "svg-001"
        top2 = system.get_top_models(leaderboard, n=2)
        assert len(top2) == 2
        assert top2[0].svg_id == "svg-001"
        assert top2[1].svg_id == "svg-002"
        top1 = system.get_top_models(leaderboard, n=1)
        assert top1[0].svg_id == "svg-001"

    def test_get_svg_stats_found(self, mock_config):
        system = RankingSystem(mock_config)
        entries = [
            LeaderboardEntry(
                rank=1,
                svg_id="svg-001",
                model_name="model_a",
                total_score=0.9,
                judgment_count=3,
                scores={"creativity": 0.9, "aesthetics": 0.8, "complexity": 0.7},
                svg_files=["file1.svg", "file2.svg"],
            ),
        ]
        leaderboard = Leaderboard(
            run_id="run-001",
            timestamp="2024-01-01T12:00:00",
            total_judgments=3,
            total_models=1,
            rankings=entries,
        )
        stats = system.get_svg_stats(leaderboard, "svg-001")
        assert stats["rank"] == 1
        assert stats["creativity"] == 0.9
        assert stats["aesthetics"] == 0.8
        assert stats["complexity"] == 0.7
        assert stats["total"] == 0.9
        assert stats["judgments_received"] == 3
        assert stats["svg_files"] == ["file1.svg", "file2.svg"]

    def test_get_svg_stats_not_found(self, mock_config):
        system = RankingSystem(mock_config)
        entries = [
            LeaderboardEntry(
                rank=1,
                svg_id="svg-001",
                model_name="model_a",
                total_score=0.9,
            ),
        ]
        leaderboard = Leaderboard(
            run_id="run-001",
            timestamp="2024-01-01T12:00:00",
            total_judgments=1,
            total_models=1,
            rankings=entries,
        )
        stats = system.get_svg_stats(leaderboard, "nonexistent")
        assert stats is None

    def test_save_leaderboard_with_run_dir(self, temp_output_dir):
        config, tmp_path = temp_output_dir
        system = RankingSystem(config)
        entries = [
            LeaderboardEntry(rank=1, svg_id="svg-001", model_name="model_a", total_score=0.9),
        ]
        leaderboard = Leaderboard(
            run_id="run-002",
            timestamp="2024-01-01T13:00:00",
            total_judgments=3,
            total_models=1,
            rankings=entries,
        )
        run_dir = tmp_path / "runs" / "run-002"
        run_dir.mkdir(parents=True, exist_ok=True)
        path = system.save_leaderboard(leaderboard, run_dir=run_dir)
        assert Path(path).exists()

    def test_load_leaderboard_not_found_raises(self, mock_config):
        system = RankingSystem(mock_config)
        with pytest.raises(FileNotFoundError):
            system.load_leaderboard("nonexistent-run")
