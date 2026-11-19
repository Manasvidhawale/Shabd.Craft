"""
Shabd.Craft — Tests: Database
"""

import sys
import os
import json
import sqlite3
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.database import Database
from src.experiment_service import duplicate_experiment
from src.schemas import (
    Experiment, PromptVersion, TestCase, EvaluationResult,
    PromptTemplate, TaskCategory, PromptingTechnique, OutputFormat,
    ExecutionStatus, EvaluationMethod, CriterionScore,
)


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    return Database(db_path)


class TestExperiments:
    def test_create_and_get(self, db):
        exp = Experiment(name="Test Experiment", category=TaskCategory.SUMMARIZATION)
        exp_id = db.create_experiment(exp)
        result = db.get_experiment(exp_id)
        assert result is not None
        assert result["name"] == "Test Experiment"
        assert result["category"] == "summarization"

    def test_list_experiments(self, db):
        db.create_experiment(Experiment(name="Exp 1"))
        db.create_experiment(Experiment(name="Exp 2"))
        exps = db.list_experiments()
        assert len(exps) == 2

    def test_delete_experiment(self, db):
        exp = Experiment(name="To Delete")
        exp_id = db.create_experiment(exp)
        db.delete_experiment(exp_id)
        assert db.get_experiment(exp_id) is None

    def test_update_status(self, db):
        exp = Experiment(name="Status Test")
        exp_id = db.create_experiment(exp)
        db.update_experiment_status(exp_id, "success")
        result = db.get_experiment(exp_id)
        assert result["status"] == "success"


class TestPromptVersions:
    def test_save_and_get(self, db):
        exp = Experiment(name="Test")
        exp_id = db.create_experiment(exp)

        version = PromptVersion(
            experiment_id=exp_id,
            system_prompt="Be helpful",
            user_prompt_template="Summarize: {{text}}",
        )
        ver_id = db.save_prompt_version(version)
        versions = db.get_prompt_versions(exp_id)
        assert len(versions) == 1
        assert versions[0]["system_prompt"] == "Be helpful"

    def test_next_version_number(self, db):
        exp = Experiment(name="Test")
        exp_id = db.create_experiment(exp)
        assert db.get_next_version_number(exp_id) == 1

        db.save_prompt_version(PromptVersion(experiment_id=exp_id, user_prompt_template="v1"))
        assert db.get_next_version_number(exp_id) == 2

    def test_first_revision_creates_main_branch(self, db):
        exp = Experiment(name="Branch Start")
        db.create_experiment(exp)
        version = PromptVersion(experiment_id=exp.id, user_prompt_template="first")
        db.save_prompt_version(version)
        branches = db.get_prompt_branches(exp.id)
        assert len(branches) == 1
        assert branches[0]["name"] == "main"
        assert branches[0]["head_version_id"] == version.id
        assert db.get_prompt_version(version.id)["branch_id"] == branches[0]["id"]

    def test_branch_forks_and_advances_without_moving_source(self, db):
        exp = Experiment(name="Named Branches")
        db.create_experiment(exp)
        root = PromptVersion(experiment_id=exp.id, user_prompt_template="root")
        db.save_prompt_version(root)
        main = db.get_prompt_branches(exp.id)[0]

        feature_id = db.create_prompt_branch(exp.id, "short-answer", root.id, "Try concise replies")
        feature_revision = PromptVersion(
            experiment_id=exp.id, branch_id=feature_id, version_number=2,
            parent_version_id=root.id, version_label="Concise",
            user_prompt_template="Answer in one sentence.",
        )
        db.save_prompt_version(feature_revision)

        assert db.get_prompt_branch(main["id"])["head_version_id"] == root.id
        assert db.get_prompt_branch(feature_id)["head_version_id"] == feature_revision.id
        assert [v["id"] for v in db.get_prompt_branch_history(feature_id)] == [root.id, feature_revision.id]

    def test_branch_names_are_unique_case_insensitively(self, db):
        exp = Experiment(name="Unique Branch Names")
        db.create_experiment(exp)
        root = PromptVersion(experiment_id=exp.id, user_prompt_template="root")
        db.save_prompt_version(root)
        db.create_prompt_branch(exp.id, "Review", root.id)
        with pytest.raises(ValueError, match="already exists"):
            db.create_prompt_branch(exp.id, "review", root.id)

    def test_branch_requires_latest_revision_as_parent(self, db):
        exp = Experiment(name="Stale Branch Head")
        db.create_experiment(exp)
        root = PromptVersion(experiment_id=exp.id, user_prompt_template="root")
        db.save_prompt_version(root)
        main = db.get_prompt_branches(exp.id)[0]
        latest = PromptVersion(
            experiment_id=exp.id, branch_id=main["id"], version_number=2,
            parent_version_id=root.id, user_prompt_template="latest",
        )
        db.save_prompt_version(latest)
        with pytest.raises(ValueError, match="branch has moved"):
            db.save_prompt_version(PromptVersion(
                experiment_id=exp.id, branch_id=main["id"], version_number=3,
                parent_version_id=root.id, user_prompt_template="stale change",
            ))

    def test_remove_branch_keeps_revisions_and_protects_main(self, db):
        exp = Experiment(name="Remove Branch")
        db.create_experiment(exp)
        root = PromptVersion(experiment_id=exp.id, user_prompt_template="root")
        db.save_prompt_version(root)
        main = db.get_prompt_branches(exp.id)[0]
        with pytest.raises(ValueError, match="main branch cannot be deleted"):
            db.delete_prompt_branch(main["id"])
        other = db.create_prompt_branch(exp.id, "try-style", root.id)
        db.delete_prompt_branch(other)
        assert db.get_prompt_branch(other) is None
        assert db.get_prompt_version(root.id) is not None


class TestTestCases:
    def test_save_and_get(self, db):
        exp = Experiment(name="Test")
        exp_id = db.create_experiment(exp)

        tc = TestCase(input_data="Test input", expected_output="Expected")
        db.save_test_case(tc, exp_id)
        cases = db.get_test_cases(exp_id)
        assert len(cases) == 1
        assert cases[0]["input_data"] == "Test input"

    def test_bulk_save(self, db):
        exp = Experiment(name="Test")
        exp_id = db.create_experiment(exp)

        tcs = [TestCase(input_data=f"Input {i}") for i in range(5)]
        db.save_test_cases_bulk(tcs, exp_id)
        assert len(db.get_test_cases(exp_id)) == 5

    def test_delete(self, db):
        exp = Experiment(name="Test")
        exp_id = db.create_experiment(exp)
        tc = TestCase(input_data="To delete")
        db.save_test_case(tc, exp_id)
        db.delete_test_case(tc.id)
        assert len(db.get_test_cases(exp_id)) == 0


class TestEvaluationResults:
    def test_save_and_get(self, db):
        exp = Experiment(name="Test")
        exp_id = db.create_experiment(exp)
        ver = PromptVersion(experiment_id=exp_id, user_prompt_template="test")
        ver_id = db.save_prompt_version(ver)
        tc = TestCase(input_data="input")
        db.save_test_case(tc, exp_id)

        er = EvaluationResult(
            test_case_id=tc.id,
            prompt_version_id=ver.id,
            experiment_id=exp_id,
            overall_score=85.0,
            execution_status=ExecutionStatus.SUCCESS,
            criterion_scores=[
                CriterionScore(name="accuracy", score=90),
                CriterionScore(name="relevance", score=80),
            ],
        )
        db.save_evaluation_result(er)
        results = db.get_evaluation_results(exp_id)
        assert len(results) == 1
        assert results[0]["overall_score"] == 85.0

    def test_bulk_save_evaluation_results(self, db):
        exp = Experiment(name="Test")
        exp_id = db.create_experiment(exp)
        ver = PromptVersion(experiment_id=exp_id, user_prompt_template="test")
        db.save_prompt_version(ver)
        tc = TestCase(input_data="input")
        db.save_test_case(tc, exp_id)

        ers = [
            EvaluationResult(
                test_case_id=tc.id,
                prompt_version_id=ver.id,
                experiment_id=exp_id,
                overall_score=float(80 + i),
                execution_status=ExecutionStatus.SUCCESS,
            ) for i in range(5)
        ]
        db.save_evaluation_results_bulk(ers)
        results = db.get_evaluation_results(exp_id)
        assert len(results) == 5


class TestDashboardMetrics:
    def test_empty_metrics(self, db):
        metrics = db.get_dashboard_metrics()
        assert metrics["total_experiments"] == 0
        assert metrics["avg_score"] == 0.0

    def test_metrics_after_data(self, db):
        exp = Experiment(name="Test")
        exp_id = db.create_experiment(exp)
        ver = PromptVersion(experiment_id=exp_id, user_prompt_template="test")
        db.save_prompt_version(ver)
        tc = TestCase(input_data="input")
        db.save_test_case(tc, exp_id)

        er = EvaluationResult(
            test_case_id=tc.id,
            prompt_version_id=ver.id,
            experiment_id=exp_id,
            overall_score=80.0,
            execution_status=ExecutionStatus.SUCCESS,
        )
        db.save_evaluation_result(er)

        metrics = db.get_dashboard_metrics()
        assert metrics["total_experiments"] == 1
        assert metrics["total_versions"] == 1
        assert metrics["avg_score"] == 80.0


class TestPromptLibrary:
    def test_save_and_get(self, db):
        tmpl = PromptTemplate(
            name="Test Template",
            user_prompt_template="Summarize: {{text}}",
            is_builtin=False,
        )
        db.save_prompt_template(tmpl)
        templates = db.get_prompt_templates()
        assert len(templates) >= 1

    def test_delete_user_template(self, db):
        tmpl = PromptTemplate(
            name="User Template",
            user_prompt_template="Test",
            is_builtin=False,
        )
        db.save_prompt_template(tmpl)
        db.delete_prompt_template(tmpl.id)
        # Should be deleted
        templates = db.get_prompt_templates(user_only=True)
        assert not any(t["id"] == tmpl.id for t in templates)

    def test_cannot_delete_builtin(self, db):
        tmpl = PromptTemplate(
            name="Builtin",
            user_prompt_template="Test",
            is_builtin=True,
        )
        db.save_prompt_template(tmpl)
        db.delete_prompt_template(tmpl.id)  # Should not delete
        templates = db.get_prompt_templates(builtin_only=True)
        assert any(t["id"] == tmpl.id for t in templates)

    def test_delete_builtin_when_allowed(self, db):
        tmpl = PromptTemplate(
            name="Builtin Removable",
            user_prompt_template="Test",
            is_builtin=True,
        )
        db.save_prompt_template(tmpl)
        db.delete_prompt_template(tmpl.id, allow_builtin=True)
        templates = db.get_prompt_templates()
        assert not any(t["id"] == tmpl.id for t in templates)


class TestVersionDeletionAndMeta:
    def test_existing_database_receives_additive_migrations(self, tmp_path):
        path = tmp_path / "legacy.db"
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE experiments (id TEXT PRIMARY KEY)")
            conn.execute("INSERT INTO experiments (id) VALUES ('legacy-exp')")
            conn.execute("CREATE TABLE prompt_versions (id TEXT PRIMARY KEY, experiment_id TEXT, version_number INTEGER, version_label TEXT, created_at TEXT)")
            conn.execute("INSERT INTO prompt_versions VALUES ('legacy-v1', 'legacy-exp', 1, 'Original', '2026-01-01')")
            conn.execute("INSERT INTO prompt_versions VALUES ('legacy-v2', 'legacy-exp', 2, 'Revision', '2026-01-02')")
            conn.execute("CREATE TABLE evaluation_results (id TEXT PRIMARY KEY, test_case_id TEXT, prompt_version_id TEXT, experiment_id TEXT)")
        migrated_db = Database(str(path))
        with sqlite3.connect(path) as conn:
            version_columns = {row[1] for row in conn.execute("PRAGMA table_info(prompt_versions)")}
            result_columns = {row[1] for row in conn.execute("PRAGMA table_info(evaluation_results)")}
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "parent_version_id" in version_columns
        assert {"evaluation_run_id", "input_data_snapshot", "expected_output_snapshot"} <= result_columns
        assert "evaluation_runs" in tables
        branch = migrated_db.get_prompt_branches("legacy-exp")[0]
        assert branch["name"] == "main"
        history = migrated_db.get_prompt_branch_history(branch["id"])
        assert [v["id"] for v in history] == ["legacy-v1", "legacy-v2"]
        assert history[1]["parent_version_id"] == "legacy-v1"

    def test_delete_prompt_version_cleans_dependencies(self, db):
        exp = Experiment(name="Ver Delete Exp")
        db.create_experiment(exp)
        pv = PromptVersion(experiment_id=exp.id, version_number=1, user_prompt_template="v1")
        db.save_prompt_version(pv)
        db.delete_prompt_version(pv.id)
        assert db.get_prompt_version(pv.id) is None
        assert db.get_prompt_versions(exp.id) == []

    def test_prompt_versions_are_immutable(self, db):
        exp = Experiment(name="Ver Update Exp")
        db.create_experiment(exp)
        pv = PromptVersion(experiment_id=exp.id, version_number=1, user_prompt_template="old")
        db.save_prompt_version(pv)
        with pytest.raises(ValueError, match="immutable"):
            db.update_prompt_version(
                version_id=pv.id,
                version_label="Edited",
                system_prompt="sys",
                user_prompt_template="new {{x}}",
                technique="zero_shot",
                output_format="text",
                model_name="gpt-4o",
                temperature=0.4,
                max_tokens=512,
                variables=["x"],
            )
        updated = db.get_prompt_version(pv.id)
        assert updated["version_label"] == "Original"
        assert updated["user_prompt_template"] == "old"

    def test_version_numbers_are_not_reused_after_delete(self, db):
        exp = Experiment(name="Monotonic Versions")
        db.create_experiment(exp)
        first = PromptVersion(experiment_id=exp.id, version_number=1, user_prompt_template="v1")
        db.save_prompt_version(first)
        second_number = db.get_next_version_number(exp.id)
        second = PromptVersion(experiment_id=exp.id, version_number=second_number, user_prompt_template="v2")
        db.save_prompt_version(second)
        db.delete_prompt_version(second.id)
        assert db.get_next_version_number(exp.id) == 3

    def test_revision_parent_must_be_in_same_experiment(self, db):
        first_exp = Experiment(name="First lineage")
        second_exp = Experiment(name="Second lineage")
        db.create_experiment(first_exp)
        db.create_experiment(second_exp)
        parent = PromptVersion(experiment_id=first_exp.id, user_prompt_template="root")
        db.save_prompt_version(parent)
        child = PromptVersion(
            experiment_id=first_exp.id, version_number=2,
            parent_version_id=parent.id, user_prompt_template="child",
        )
        db.save_prompt_version(child)
        assert db.get_prompt_version(child.id)["parent_version_id"] == parent.id
        with pytest.raises(ValueError, match="same experiment"):
            db.save_prompt_version(PromptVersion(
                experiment_id=second_exp.id, parent_version_id=parent.id,
                user_prompt_template="invalid child",
            ))

    def test_duplicate_experiment_preserves_named_branches(self, db):
        exp = Experiment(name="Original branches")
        db.create_experiment(exp)
        root = PromptVersion(experiment_id=exp.id, user_prompt_template="root")
        db.save_prompt_version(root)
        main = db.get_prompt_branches(exp.id)[0]
        main_revision = PromptVersion(
            experiment_id=exp.id, branch_id=main["id"], version_number=2,
            parent_version_id=root.id, user_prompt_template="main change",
        )
        db.save_prompt_version(main_revision)
        variant_id = db.create_prompt_branch(exp.id, "variant", root.id)
        variant_revision = PromptVersion(
            experiment_id=exp.id, branch_id=variant_id, version_number=3,
            parent_version_id=root.id, user_prompt_template="variant change",
        )
        db.save_prompt_version(variant_revision)
        db.save_test_case(TestCase(input_data="case", metadata={"kind": "sample"}), exp.id)

        duplicate_id = duplicate_experiment(db, exp.id, "Copied branches")
        copied_branches = {branch["name"]: branch for branch in db.get_prompt_branches(duplicate_id)}
        assert set(copied_branches) == {"main", "variant"}
        main_history = db.get_prompt_branch_history(copied_branches["main"]["id"])
        variant_history = db.get_prompt_branch_history(copied_branches["variant"]["id"])
        assert len(main_history) == 2
        assert len(variant_history) == 2
        assert main_history[0]["id"] == variant_history[0]["id"]
        assert main_history[0]["id"] != root.id
        assert db.get_test_cases(duplicate_id)[0]["metadata"] == '{"kind": "sample"}'

    def test_evaluation_run_keeps_case_snapshot_and_settings_signature(self, db):
        exp = Experiment(name="Run Snapshot")
        db.create_experiment(exp)
        version = PromptVersion(experiment_id=exp.id, user_prompt_template="{{input}}")
        db.save_prompt_version(version)
        case = TestCase(input_data="original input", expected_output="original reference")
        db.save_test_case(case, exp.id)
        run_id = db.create_evaluation_run(
            exp.id, version.id, "rule_based", {"accuracy": 1.0}, {"max_words": 20},
            [{"id": case.id, "input_data": case.input_data, "expected_output": case.expected_output}],
        )
        db.update_test_case(case.id, "edited input", "edited reference")
        run = db.get_evaluation_runs(exp.id, version.id)[0]
        assert run["id"] == run_id
        assert json.loads(run["test_cases_snapshot"])[0]["input_data"] == "original input"
        changed_run_id = db.create_evaluation_run(
            exp.id, version.id, "rule_based", {"accuracy": 0.5}, {"max_words": 20},
            [{"id": case.id, "input_data": "original input", "expected_output": "original reference"}],
        )
        other_run = next(r for r in db.get_evaluation_runs(exp.id, version.id) if r["id"] == changed_run_id)
        assert other_run["signature"] != run["signature"]

    def test_evaluation_result_keeps_input_snapshot(self, db):
        exp = Experiment(name="Result Snapshot")
        db.create_experiment(exp)
        version = PromptVersion(experiment_id=exp.id, user_prompt_template="{{input}}")
        db.save_prompt_version(version)
        case = TestCase(input_data="input before edit", expected_output="reference before edit")
        db.save_test_case(case, exp.id)
        run_id = db.create_evaluation_run(exp.id, version.id, "rule_based", {}, {}, [case.model_dump()])
        result = EvaluationResult(
            test_case_id=case.id, prompt_version_id=version.id, experiment_id=exp.id,
            evaluation_run_id=run_id, input_data_snapshot=case.input_data,
            expected_output_snapshot=case.expected_output,
        )
        db.save_evaluation_result(result)
        db.update_test_case(case.id, "input after edit", "reference after edit")
        stored = db.get_evaluation_results(exp.id, evaluation_run_id=run_id)[0]
        assert stored["input_data_snapshot"] == "input before edit"
        assert stored["expected_output_snapshot"] == "reference before edit"

    def test_comparable_runs_require_matching_snapshot_and_settings(self, db):
        exp = Experiment(name="Comparable Runs")
        db.create_experiment(exp)
        version_a = PromptVersion(experiment_id=exp.id, user_prompt_template="A")
        version_b = PromptVersion(experiment_id=exp.id, version_number=2, user_prompt_template="B")
        db.save_prompt_version(version_a)
        db.save_prompt_version(version_b)
        cases = [{"id": "tc-1", "input_data": "one", "expected_output": "gold"}]
        run_a = db.create_evaluation_run(exp.id, version_a.id, "rule_based", {"accuracy": 1}, {}, cases)
        run_b = db.create_evaluation_run(exp.id, version_b.id, "rule_based", {"accuracy": 1}, {}, cases)
        db.update_evaluation_run_status(run_a, "done")
        db.update_evaluation_run_status(run_b, "done")
        pairs = db.get_comparable_evaluation_run_pairs(exp.id, version_a.id, version_b.id)
        assert [(a["id"], b["id"]) for a, b in pairs] == [(run_a, run_b)]

        incomplete = db.create_evaluation_run(exp.id, version_b.id, "rule_based", {"accuracy": 0.5}, {}, cases)
        db.update_evaluation_run_status(incomplete, "done")
        pairs = db.get_comparable_evaluation_run_pairs(exp.id, version_a.id, version_b.id)
        assert len(pairs) == 1

    def test_app_meta_roundtrip(self, db):
        assert db.get_meta("missing", "fallback") == "fallback"
        db.set_meta("templates_seeded", "1")
        assert db.get_meta("templates_seeded") == "1"
