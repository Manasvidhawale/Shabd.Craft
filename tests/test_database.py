"""
Shabd.Craft — Tests: Database
"""

import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.database import Database
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
    def test_delete_prompt_version_cleans_dependencies(self, db):
        exp = Experiment(name="Ver Delete Exp")
        db.create_experiment(exp)
        pv = PromptVersion(experiment_id=exp.id, version_number=1, user_prompt_template="v1")
        db.save_prompt_version(pv)
        db.delete_prompt_version(pv.id)
        assert db.get_prompt_version(pv.id) is None
        assert db.get_prompt_versions(exp.id) == []

    def test_update_prompt_version(self, db):
        exp = Experiment(name="Ver Update Exp")
        db.create_experiment(exp)
        pv = PromptVersion(experiment_id=exp.id, version_number=1, user_prompt_template="old")
        db.save_prompt_version(pv)
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
        assert updated["version_label"] == "Edited"
        assert updated["user_prompt_template"] == "new {{x}}"

    def test_app_meta_roundtrip(self, db):
        assert db.get_meta("missing", "fallback") == "fallback"
        db.set_meta("templates_seeded", "1")
        assert db.get_meta("templates_seeded") == "1"
