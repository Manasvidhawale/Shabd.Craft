"""
Shabd.Craft — SQLite Database Layer

Persistent storage for experiments, prompt versions, test cases,
evaluation results, and prompt library entries.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from src.schemas import (
    Experiment, PromptVersion, TestCase, EvaluationResult,
    PromptTemplate, OptimizationCandidate, ExecutionStatus,
    TaskCategory, _new_id, _now,
)


class Database:
    """SQLite database manager for Shabd.Craft."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    description TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS prompt_versions (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    version_number INTEGER DEFAULT 1,
                    version_label TEXT DEFAULT 'Original',
                    system_prompt TEXT DEFAULT '',
                    user_prompt_template TEXT NOT NULL,
                    technique TEXT DEFAULT 'zero_shot',
                    few_shot_examples TEXT DEFAULT '[]',
                    output_format TEXT DEFAULT 'text',
                    variables TEXT DEFAULT '[]',
                    model_name TEXT DEFAULT '',
                    temperature REAL DEFAULT 0.7,
                    max_tokens INTEGER DEFAULT 1024,
                    is_optimized INTEGER DEFAULT 0,
                    optimization_strategy TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                );

                CREATE TABLE IF NOT EXISTS test_cases (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    input_data TEXT NOT NULL,
                    expected_output TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                );

                CREATE TABLE IF NOT EXISTS evaluation_results (
                    id TEXT PRIMARY KEY,
                    test_case_id TEXT NOT NULL,
                    prompt_version_id TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    generated_output TEXT DEFAULT '',
                    criterion_scores TEXT DEFAULT '[]',
                    overall_score REAL DEFAULT 0.0,
                    weaknesses TEXT DEFAULT '[]',
                    suggestions TEXT DEFAULT '[]',
                    evaluation_method TEXT DEFAULT 'rule_based',
                    is_reference_verified INTEGER DEFAULT 0,
                    execution_status TEXT DEFAULT 'pending',
                    error_message TEXT DEFAULT '',
                    latency_ms REAL DEFAULT 0.0,
                    tokens_used INTEGER DEFAULT 0,
                    cost_estimate REAL DEFAULT 0.0,
                    is_demo INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (test_case_id) REFERENCES test_cases(id),
                    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id),
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                );

                CREATE TABLE IF NOT EXISTS optimization_candidates (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    original_version_id TEXT NOT NULL,
                    candidate_label TEXT DEFAULT 'Candidate A',
                    strategy TEXT DEFAULT '',
                    system_prompt TEXT DEFAULT '',
                    user_prompt_template TEXT NOT NULL,
                    changes_description TEXT DEFAULT '',
                    rationale TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    overall_score REAL DEFAULT 0.0,
                    is_accepted INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
                    FOREIGN KEY (original_version_id) REFERENCES prompt_versions(id)
                );

                CREATE TABLE IF NOT EXISTS prompt_library (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT 'general',
                    system_prompt TEXT DEFAULT '',
                    user_prompt_template TEXT NOT NULL,
                    variables TEXT DEFAULT '[]',
                    technique TEXT DEFAULT 'zero_shot',
                    few_shot_examples TEXT DEFAULT '[]',
                    output_format TEXT DEFAULT 'text',
                    example_input TEXT DEFAULT '',
                    example_output TEXT DEFAULT '',
                    eval_criteria TEXT DEFAULT '{}',
                    is_builtin INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pv_experiment ON prompt_versions(experiment_id);
                CREATE INDEX IF NOT EXISTS idx_tc_experiment ON test_cases(experiment_id);
                CREATE INDEX IF NOT EXISTS idx_er_experiment ON evaluation_results(experiment_id);
                CREATE INDEX IF NOT EXISTS idx_er_version ON evaluation_results(prompt_version_id);
                CREATE INDEX IF NOT EXISTS idx_oc_experiment ON optimization_candidates(experiment_id);
            """)

    # ── Experiments ────────────────────────────────────────────────────

    def create_experiment(self, exp: Experiment) -> str:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO experiments (id, name, category, description, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (exp.id, exp.name, exp.category.value, exp.description,
                 exp.status.value, exp.created_at, exp.updated_at),
            )
        return exp.id

    def get_experiment(self, exp_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,)).fetchone()
            return dict(row) if row else None

    def list_experiments(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_experiment_status(self, exp_id: str, status: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE experiments SET status = ?, updated_at = ? WHERE id = ?",
                (status, _now(), exp_id),
            )

    def delete_experiment(self, exp_id: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM evaluation_results WHERE experiment_id = ?", (exp_id,))
            conn.execute("DELETE FROM optimization_candidates WHERE experiment_id = ?", (exp_id,))
            conn.execute("DELETE FROM test_cases WHERE experiment_id = ?", (exp_id,))
            conn.execute("DELETE FROM prompt_versions WHERE experiment_id = ?", (exp_id,))
            conn.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))

    # ── Prompt Versions ────────────────────────────────────────────────

    def save_prompt_version(self, pv: PromptVersion) -> str:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO prompt_versions "
                "(id, experiment_id, version_number, version_label, system_prompt, "
                "user_prompt_template, technique, few_shot_examples, output_format, "
                "variables, model_name, temperature, max_tokens, is_optimized, "
                "optimization_strategy, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pv.id, pv.experiment_id, pv.version_number, pv.version_label,
                 pv.system_prompt, pv.user_prompt_template, pv.technique.value,
                 json.dumps([e.model_dump() for e in pv.few_shot_examples]),
                 pv.output_format.value, json.dumps(pv.variables),
                 pv.model_name, pv.temperature, pv.max_tokens,
                 1 if pv.is_optimized else 0, pv.optimization_strategy,
                 pv.created_at),
            )
        return pv.id

    def get_prompt_versions(self, experiment_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM prompt_versions WHERE experiment_id = ? ORDER BY version_number",
                (experiment_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_prompt_version(self, version_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM prompt_versions WHERE id = ?", (version_id,)).fetchone()
            return dict(row) if row else None

    def get_next_version_number(self, experiment_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(version_number) as mx FROM prompt_versions WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
            return (row["mx"] or 0) + 1

    # ── Test Cases ─────────────────────────────────────────────────────

    def save_test_case(self, tc: TestCase, experiment_id: str) -> str:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO test_cases (id, experiment_id, input_data, expected_output, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (tc.id, experiment_id, tc.input_data, tc.expected_output,
                 json.dumps(tc.metadata)),
            )
        return tc.id

    def save_test_cases_bulk(self, test_cases: list[TestCase], experiment_id: str):
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO test_cases (id, experiment_id, input_data, expected_output, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                [(tc.id, experiment_id, tc.input_data, tc.expected_output,
                  json.dumps(tc.metadata)) for tc in test_cases],
            )

    def get_test_cases(self, experiment_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM test_cases WHERE experiment_id = ?", (experiment_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_test_case(self, tc_id: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM evaluation_results WHERE test_case_id = ?", (tc_id,))
            conn.execute("DELETE FROM test_cases WHERE id = ?", (tc_id,))

    def update_test_case(self, tc_id: str, input_data: str, expected_output: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE test_cases SET input_data = ?, expected_output = ? WHERE id = ?",
                (input_data, expected_output, tc_id),
            )

    # ── Evaluation Results ─────────────────────────────────────────────

    def save_evaluation_result(self, er: EvaluationResult) -> str:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO evaluation_results "
                "(id, test_case_id, prompt_version_id, experiment_id, generated_output, "
                "criterion_scores, overall_score, weaknesses, suggestions, "
                "evaluation_method, is_reference_verified, execution_status, "
                "error_message, latency_ms, tokens_used, cost_estimate, is_demo, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (er.id, er.test_case_id, er.prompt_version_id, er.experiment_id,
                 er.generated_output,
                 json.dumps([s.model_dump() for s in er.criterion_scores]),
                 er.overall_score,
                 json.dumps(er.weaknesses), json.dumps(er.suggestions),
                 er.evaluation_method.value,
                 1 if er.is_reference_verified else 0,
                 er.execution_status.value, er.error_message,
                 er.latency_ms, er.tokens_used, er.cost_estimate,
                 1 if er.is_demo else 0, er.created_at),
            )
        return er.id

    def get_evaluation_results(self, experiment_id: str, prompt_version_id: Optional[str] = None) -> list[dict]:
        with self._connect() as conn:
            if prompt_version_id:
                rows = conn.execute(
                    "SELECT * FROM evaluation_results WHERE experiment_id = ? AND prompt_version_id = ? "
                    "ORDER BY created_at",
                    (experiment_id, prompt_version_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM evaluation_results WHERE experiment_id = ? ORDER BY created_at",
                    (experiment_id,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_all_evaluation_scores(self) -> list[dict]:
        """Get all evaluation scores for dashboard metrics."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT er.*, e.name as experiment_name, e.category, "
                "pv.version_label, pv.version_number "
                "FROM evaluation_results er "
                "JOIN experiments e ON er.experiment_id = e.id "
                "JOIN prompt_versions pv ON er.prompt_version_id = pv.id "
                "WHERE er.execution_status = 'success' "
                "ORDER BY er.created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Optimization Candidates ────────────────────────────────────────

    def save_optimization_candidate(self, oc: OptimizationCandidate) -> str:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO optimization_candidates "
                "(id, experiment_id, original_version_id, candidate_label, strategy, "
                "system_prompt, user_prompt_template, changes_description, rationale, "
                "status, overall_score, is_accepted, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (oc.id, oc.experiment_id, oc.original_version_id, oc.candidate_label,
                 oc.strategy, oc.system_prompt, oc.user_prompt_template,
                 oc.changes_description, oc.rationale, oc.status.value,
                 oc.overall_score, 1 if oc.is_accepted else 0, oc.created_at),
            )
        return oc.id

    def get_optimization_candidates(self, experiment_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM optimization_candidates WHERE experiment_id = ? ORDER BY created_at",
                (experiment_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_candidate_score(self, candidate_id: str, score: float, status: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE optimization_candidates SET overall_score = ?, status = ? WHERE id = ?",
                (score, status, candidate_id),
            )

    def accept_candidate(self, candidate_id: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE optimization_candidates SET is_accepted = 1 WHERE id = ?",
                (candidate_id,),
            )

    # ── Prompt Library ─────────────────────────────────────────────────

    def save_prompt_template(self, pt: PromptTemplate) -> str:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO prompt_library "
                "(id, name, description, category, system_prompt, user_prompt_template, "
                "variables, technique, few_shot_examples, output_format, "
                "example_input, example_output, eval_criteria, is_builtin, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pt.id, pt.name, pt.description, pt.category.value,
                 pt.system_prompt, pt.user_prompt_template,
                 json.dumps(pt.variables), pt.technique.value,
                 json.dumps([e.model_dump() for e in pt.few_shot_examples]),
                 pt.output_format.value, pt.example_input, pt.example_output,
                 json.dumps(pt.eval_criteria),
                 1 if pt.is_builtin else 0, pt.created_at, pt.updated_at),
            )
        return pt.id

    def get_prompt_templates(self, builtin_only: bool = False, user_only: bool = False) -> list[dict]:
        with self._connect() as conn:
            if builtin_only:
                rows = conn.execute(
                    "SELECT * FROM prompt_library WHERE is_builtin = 1 ORDER BY category, name"
                ).fetchall()
            elif user_only:
                rows = conn.execute(
                    "SELECT * FROM prompt_library WHERE is_builtin = 0 ORDER BY updated_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM prompt_library ORDER BY is_builtin DESC, category, name"
                ).fetchall()
            return [dict(r) for r in rows]

    def delete_prompt_template(self, template_id: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM prompt_library WHERE id = ? AND is_builtin = 0", (template_id,))

    # ── Dashboard Metrics ──────────────────────────────────────────────

    def get_dashboard_metrics(self) -> dict:
        with self._connect() as conn:
            total_experiments = conn.execute("SELECT COUNT(*) as c FROM experiments").fetchone()["c"]
            total_versions = conn.execute("SELECT COUNT(*) as c FROM prompt_versions").fetchone()["c"]
            total_test_cases = conn.execute(
                "SELECT COUNT(DISTINCT test_case_id) as c FROM evaluation_results"
            ).fetchone()["c"]
            avg_score_row = conn.execute(
                "SELECT AVG(overall_score) as avg FROM evaluation_results WHERE execution_status = 'success'"
            ).fetchone()
            avg_score = round(avg_score_row["avg"], 1) if avg_score_row["avg"] is not None else 0.0

            best_row = conn.execute(
                "SELECT pv.version_label, e.name, er.overall_score "
                "FROM evaluation_results er "
                "JOIN prompt_versions pv ON er.prompt_version_id = pv.id "
                "JOIN experiments e ON er.experiment_id = e.id "
                "WHERE er.execution_status = 'success' "
                "ORDER BY er.overall_score DESC LIMIT 1"
            ).fetchone()
            best_prompt = ""
            if best_row:
                best_prompt = f"{best_row['name']} — {best_row['version_label']} ({best_row['overall_score']:.0f})"

            optimization_count = conn.execute(
                "SELECT COUNT(DISTINCT experiment_id) as c FROM optimization_candidates"
            ).fetchone()["c"]

            return {
                "total_experiments": total_experiments,
                "total_versions": total_versions,
                "total_test_cases": total_test_cases,
                "avg_score": avg_score,
                "best_prompt": best_prompt,
                "optimization_count": optimization_count,
            }

    def get_recent_experiments(self, limit: int = 10) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT e.*,
                    (SELECT AVG(er.overall_score) FROM evaluation_results er
                     WHERE er.experiment_id = e.id AND er.execution_status = 'success') as avg_score,
                    (SELECT COUNT(*) FROM prompt_versions pv WHERE pv.experiment_id = e.id) as version_count
                FROM experiments e
                ORDER BY e.updated_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_criterion_averages(self) -> dict[str, float]:
        """Get average scores by criterion across all successful evaluations."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT criterion_scores FROM evaluation_results WHERE execution_status = 'success'"
            ).fetchall()

        if not rows:
            return {}

        totals: dict[str, list[float]] = {}
        for row in rows:
            scores = json.loads(row["criterion_scores"])
            for s in scores:
                name = s.get("name", "")
                score = s.get("score", 0)
                if name:
                    totals.setdefault(name, []).append(score)

        return {k: round(sum(v) / len(v), 1) for k, v in totals.items()}
