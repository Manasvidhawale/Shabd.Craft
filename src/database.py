"""
Shabd.Craft — SQLite Database Layer

Persistent storage for experiments, prompt versions, test cases,
evaluation results, and prompt library entries.
"""

from __future__ import annotations

import json
import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from src.schemas import (
    Experiment, PromptVersion, PromptBranch, TestCase, EvaluationResult,
    PromptTemplate, OptimizationCandidate, ExecutionStatus,
    TaskCategory, PromptingTechnique, OutputFormat, FewShotExample,
    _new_id, _now,
)


class Database:
    """SQLite database manager for Shabd.Craft."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
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
                    branch_id TEXT,
                    version_number INTEGER DEFAULT 1,
                    parent_version_id TEXT,
                    parent_2_version_id TEXT,
                    merge_metadata TEXT DEFAULT '',
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

                CREATE TABLE IF NOT EXISTS prompt_branches (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    name TEXT NOT NULL COLLATE NOCASE,
                    head_version_id TEXT NOT NULL,
                    base_version_id TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (experiment_id, name),
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
                    FOREIGN KEY (head_version_id) REFERENCES prompt_versions(id),
                    FOREIGN KEY (base_version_id) REFERENCES prompt_versions(id)
                );

                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    prompt_version_id TEXT NOT NULL,
                    method TEXT NOT NULL,
                    weights TEXT NOT NULL DEFAULT '{}',
                    config TEXT NOT NULL DEFAULT '{}',
                    test_cases_snapshot TEXT NOT NULL DEFAULT '[]',
                    signature TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'running',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
                    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id)
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
                    evaluation_run_id TEXT,
                    input_data_snapshot TEXT DEFAULT '',
                    expected_output_snapshot TEXT DEFAULT '',
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

                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pv_experiment ON prompt_versions(experiment_id);
                CREATE INDEX IF NOT EXISTS idx_tc_experiment ON test_cases(experiment_id);
                CREATE INDEX IF NOT EXISTS idx_er_experiment ON evaluation_results(experiment_id);
                CREATE INDEX IF NOT EXISTS idx_er_version ON evaluation_results(prompt_version_id);
                CREATE INDEX IF NOT EXISTS idx_oc_experiment ON optimization_candidates(experiment_id);
                CREATE INDEX IF NOT EXISTS idx_run_version ON evaluation_runs(prompt_version_id, created_at);
            """)
            # Additive migrations keep existing local workspaces readable.
            for table, column, definition in (
                ("prompt_versions", "branch_id", "TEXT"),
                ("prompt_versions", "parent_version_id", "TEXT"),
                ("prompt_versions", "parent_2_version_id", "TEXT"),
                ("prompt_versions", "merge_metadata", "TEXT DEFAULT ''"),
                ("evaluation_results", "evaluation_run_id", "TEXT"),
                ("evaluation_results", "input_data_snapshot", "TEXT DEFAULT ''"),
                ("evaluation_results", "expected_output_snapshot", "TEXT DEFAULT ''"),
            ):
                columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
                if column not in columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pv_branch ON prompt_versions(branch_id)")

            # Give pre-branch experiments a main branch while preserving their existing revisions.
            experiments = conn.execute("SELECT id FROM experiments").fetchall()
            for experiment in experiments:
                exp_id = experiment["id"]
                has_branch = conn.execute(
                    "SELECT 1 FROM prompt_branches WHERE experiment_id = ? LIMIT 1", (exp_id,)
                ).fetchone()
                if has_branch:
                    continue
                revisions = conn.execute(
                    "SELECT id, parent_version_id FROM prompt_versions WHERE experiment_id = ? "
                    "ORDER BY version_number, created_at, rowid", (exp_id,)
                ).fetchall()
                if not revisions:
                    continue
                # Pre-branch versions were numbered linearly but had no parent links.
                for index, revision in enumerate(revisions):
                    if index and not revision["parent_version_id"]:
                        conn.execute(
                            "UPDATE prompt_versions SET parent_version_id = ? WHERE id = ?",
                            (revisions[index - 1]["id"], revision["id"]),
                        )
                base_id = revisions[0]["id"]
                head_id = revisions[-1]["id"]
                branch_id = _new_id()
                now = _now()
                conn.execute(
                    "INSERT INTO prompt_branches (id, experiment_id, name, head_version_id, base_version_id, description, created_at, updated_at) "
                    "VALUES (?, ?, 'main', ?, ?, 'Default branch created during migration', ?, ?)",
                    (branch_id, exp_id, head_id, base_id, now, now),
                )
                conn.execute("UPDATE prompt_versions SET branch_id = ? WHERE experiment_id = ?", (branch_id, exp_id))

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
            conn.execute("DELETE FROM evaluation_runs WHERE experiment_id = ?", (exp_id,))
            conn.execute("DELETE FROM evaluation_results WHERE experiment_id = ?", (exp_id,))
            conn.execute("DELETE FROM optimization_candidates WHERE experiment_id = ?", (exp_id,))
            conn.execute("DELETE FROM test_cases WHERE experiment_id = ?", (exp_id,))
            conn.execute("DELETE FROM prompt_branches WHERE experiment_id = ?", (exp_id,))
            conn.execute("DELETE FROM prompt_versions WHERE experiment_id = ?", (exp_id,))
            conn.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))

    # ── Prompt Branches ─────────────────────────────────────────────────

    def create_prompt_branch(
        self, experiment_id: str, name: str, source_version_id: str,
        description: str = "",
    ) -> str:
        """Create a named branch whose initial head is an existing revision."""
        branch_name = name.strip()
        if not branch_name or len(branch_name) > 60:
            raise ValueError("Branch names must contain 1 to 60 characters.")
        branch = PromptBranch(
            experiment_id=experiment_id,
            name=branch_name,
            head_version_id=source_version_id,
            base_version_id=source_version_id,
            description=description.strip(),
        )
        with self._connect() as conn:
            source = conn.execute(
                "SELECT experiment_id FROM prompt_versions WHERE id = ?", (source_version_id,)
            ).fetchone()
            if not source or source["experiment_id"] != experiment_id:
                raise ValueError("Choose a revision from this experiment as the branch starting point.")
            try:
                conn.execute(
                    "INSERT INTO prompt_branches (id, experiment_id, name, head_version_id, base_version_id, description, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (branch.id, branch.experiment_id, branch.name, branch.head_version_id,
                     branch.base_version_id, branch.description, branch.created_at, branch.updated_at),
                )
            except sqlite3.IntegrityError as exc:
                if "prompt_branches.experiment_id, prompt_branches.name" in str(exc):
                    raise ValueError(f"A branch named '{branch_name}' already exists in this experiment.") from exc
                raise
        return branch.id

    def get_prompt_branches(self, experiment_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT b.*, pv.version_number AS head_version_number, pv.version_label AS head_version_label "
                "FROM prompt_branches b LEFT JOIN prompt_versions pv ON pv.id = b.head_version_id "
                "WHERE b.experiment_id = ? ORDER BY CASE WHEN b.name = 'main' COLLATE NOCASE THEN 0 ELSE 1 END, b.name COLLATE NOCASE",
                (experiment_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_prompt_branch(self, branch_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT b.*, pv.version_number AS head_version_number, pv.version_label AS head_version_label "
                "FROM prompt_branches b LEFT JOIN prompt_versions pv ON pv.id = b.head_version_id "
                "WHERE b.id = ?", (branch_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_prompt_branch_history(self, branch_id: str) -> list[dict]:
        """Return revisions from the branch's starting point through its head."""
        branch = self.get_prompt_branch(branch_id)
        if not branch:
            return []
        by_id = {v["id"]: v for v in self.get_prompt_versions(branch["experiment_id"])}
        history = []
        current_id = branch["head_version_id"]
        visited = set()
        while current_id and current_id in by_id and current_id not in visited:
            visited.add(current_id)
            version = by_id[current_id]
            history.append(version)
            if current_id == branch["base_version_id"]:
                break
            current_id = version.get("parent_version_id")
        return list(reversed(history))

    def delete_prompt_branch(self, branch_id: str):
        """Remove a non-main branch pointer while keeping its immutable revisions."""
        with self._connect() as conn:
            branch = conn.execute("SELECT * FROM prompt_branches WHERE id = ?", (branch_id,)).fetchone()
            if not branch:
                return
            if branch["name"].lower() == "main":
                raise ValueError("The main branch cannot be deleted.")
            conn.execute("UPDATE prompt_versions SET branch_id = NULL WHERE branch_id = ?", (branch_id,))
            conn.execute("DELETE FROM prompt_branches WHERE id = ?", (branch_id,))

    # ── Branch Merging & Lineage Ancestry ─────────────────────────────

    def find_lowest_common_ancestor(
        self, experiment_id: str, ver_a_id: str, ver_b_id: str
    ) -> Optional[dict]:
        """
        Find the lowest common ancestor (LCA) between two revisions in an experiment.
        Traverses DAG edges through both parent_version_id and parent_2_version_id.
        Returns the ancestor PromptVersion dict, or None if no common ancestor exists.
        """
        with self._connect() as conn:
            all_versions = {
                row["id"]: dict(row)
                for row in conn.execute(
                    "SELECT * FROM prompt_versions WHERE experiment_id = ?", (experiment_id,)
                ).fetchall()
            }

        if ver_a_id not in all_versions or ver_b_id not in all_versions:
            return None

        if ver_a_id == ver_b_id:
            return all_versions[ver_a_id]

        def get_ancestors_with_depth(start_id: str) -> dict[str, int]:
            visited: dict[str, int] = {}
            queue = [(start_id, 0)]
            while queue:
                curr_id, depth = queue.pop(0)
                if curr_id in visited and visited[curr_id] <= depth:
                    continue
                visited[curr_id] = depth
                node = all_versions.get(curr_id)
                if not node:
                    continue
                p1 = node.get("parent_version_id")
                if p1 and p1 in all_versions:
                    queue.append((p1, depth + 1))
                p2 = node.get("parent_2_version_id")
                if p2 and p2 in all_versions:
                    queue.append((p2, depth + 1))
            return visited

        anc_a = get_ancestors_with_depth(ver_a_id)
        anc_b = get_ancestors_with_depth(ver_b_id)

        common_ids = set(anc_a.keys()) & set(anc_b.keys())
        if not common_ids:
            return None

        # Return lowest common ancestor (highest version_number, closest to both branch tips)
        best_id = max(
            common_ids,
            key=lambda cid: (all_versions[cid]["version_number"], -(anc_a[cid] + anc_b[cid])),
        )
        return all_versions[best_id]

    def compute_three_way_merge(
        self, ancestor: dict, dest_version: dict, source_version: dict
    ) -> dict:
        """
        Compute a 3-way merge between destination and source relative to ancestor.
        Inspects all prompt fields, determines automatic resolutions, and flags conflicts.
        """
        fields_to_check = [
            "system_prompt",
            "user_prompt_template",
            "technique",
            "output_format",
            "model_name",
            "temperature",
            "max_tokens",
            "few_shot_examples",
        ]

        result_fields: dict[str, dict] = {}
        conflicts: list[str] = []
        auto_merged: list[str] = []
        unchanged: list[str] = []

        for field in fields_to_check:
            a_val = ancestor.get(field)
            d_val = dest_version.get(field)
            s_val = source_version.get(field)

            # Normalize few_shot_examples if stored as JSON string
            if field == "few_shot_examples":
                if isinstance(a_val, str):
                    try:
                        a_val = json.loads(a_val)
                    except Exception:
                        a_val = []
                if isinstance(d_val, str):
                    try:
                        d_val = json.loads(d_val)
                    except Exception:
                        d_val = []
                if isinstance(s_val, str):
                    try:
                        s_val = json.loads(s_val)
                    except Exception:
                        s_val = []

            # Compare values
            d_changed = (d_val != a_val)
            s_changed = (s_val != a_val)

            if not d_changed and not s_changed:
                status = "unchanged"
                proposed = d_val
                is_conflict = False
                unchanged.append(field)
            elif not d_changed and s_changed:
                status = "auto_source"
                proposed = s_val
                is_conflict = False
                auto_merged.append(field)
            elif d_changed and not s_changed:
                status = "auto_dest"
                proposed = d_val
                is_conflict = False
                auto_merged.append(field)
            elif d_val == s_val:
                status = "auto_same"
                proposed = d_val
                is_conflict = False
                auto_merged.append(field)
            else:
                status = "conflict"
                proposed = d_val  # Default to destination value
                is_conflict = True
                conflicts.append(field)

            result_fields[field] = {
                "field": field,
                "ancestor": a_val,
                "destination": d_val,
                "source": s_val,
                "proposed": proposed,
                "status": status,
                "is_conflict": is_conflict,
            }

        return {
            "has_conflicts": len(conflicts) > 0,
            "conflicts": conflicts,
            "auto_merged": auto_merged,
            "unchanged": unchanged,
            "fields": result_fields,
            "ancestor_version_id": ancestor.get("id"),
            "dest_version_id": dest_version.get("id"),
            "source_version_id": source_version.get("id"),
        }

    def execute_fast_forward_merge(
        self,
        experiment_id: str,
        dest_branch_id: str,
        source_branch_id: str,
        expected_dest_head_id: str | None = None,
        expected_source_head_id: str | None = None,
    ) -> dict:
        """
        Advance dest_branch head directly to source_branch head when dest is an ancestor of source.
        Guarantees fast-forward safety.
        """
        with self._connect() as conn:
            dest_branch = conn.execute(
                "SELECT * FROM prompt_branches WHERE id = ?", (dest_branch_id,)
            ).fetchone()
            src_branch = conn.execute(
                "SELECT * FROM prompt_branches WHERE id = ?", (source_branch_id,)
            ).fetchone()
            if not dest_branch or not src_branch:
                raise ValueError("Both destination and source branches must exist.")
            if dest_branch["experiment_id"] != experiment_id or src_branch["experiment_id"] != experiment_id:
                raise ValueError("Both branches must belong to this experiment.")
            if dest_branch["id"] == src_branch["id"]:
                raise ValueError("Cannot merge a branch into itself.")

            dest_head_id = dest_branch["head_version_id"]
            src_head_id = src_branch["head_version_id"]
            if expected_dest_head_id and dest_head_id != expected_dest_head_id:
                raise ValueError("Destination branch has been updated since preview. Please refresh and review the merge again.")
            if expected_source_head_id and src_head_id != expected_source_head_id:
                raise ValueError("Source branch has been updated since preview. Please refresh and review the merge again.")
            if dest_head_id == src_head_id:
                raise ValueError("Branches are already pointing to the same revision.")

            ancestor = self.find_lowest_common_ancestor(experiment_id, dest_head_id, src_head_id)
            if not ancestor or ancestor["id"] != dest_head_id:
                raise ValueError("Fast-forward merge not possible: destination branch has diverged.")

            now = _now()
            conn.execute(
                "UPDATE prompt_branches SET head_version_id = ?, updated_at = ? WHERE id = ?",
                (src_head_id, now, dest_branch_id),
            )
            src_version = conn.execute(
                "SELECT * FROM prompt_versions WHERE id = ?", (src_head_id,)
            ).fetchone()
            return {
                "version_id": src_head_id,
                "version_number": src_version["version_number"],
                "is_fast_forward": True,
            }

    def execute_branch_merge(
        self,
        experiment_id: str,
        dest_branch_id: str,
        source_branch_id: str,
        resolved_fields: dict,
        custom_label: str = "",
        expected_dest_head_id: str | None = None,
        expected_source_head_id: str | None = None,
    ) -> dict:
        """
        Create an immutable merge version combining dest and source branches,
        recording both parents and merge metadata, and advancing destination branch head.
        """
        with self._connect() as conn:
            dest_branch = conn.execute(
                "SELECT * FROM prompt_branches WHERE id = ?", (dest_branch_id,)
            ).fetchone()
            src_branch = conn.execute(
                "SELECT * FROM prompt_branches WHERE id = ?", (source_branch_id,)
            ).fetchone()
            if not dest_branch or not src_branch:
                raise ValueError("Both destination and source branches must exist.")
            if dest_branch["experiment_id"] != experiment_id or src_branch["experiment_id"] != experiment_id:
                raise ValueError("Both branches must belong to this experiment.")
            if dest_branch["id"] == src_branch["id"]:
                raise ValueError("Cannot merge a branch into itself.")

            dest_head_id = dest_branch["head_version_id"]
            src_head_id = src_branch["head_version_id"]
            if expected_dest_head_id and dest_head_id != expected_dest_head_id:
                raise ValueError("Destination branch has been updated since preview. Please refresh and review the merge again.")
            if expected_source_head_id and src_head_id != expected_source_head_id:
                raise ValueError("Source branch has been updated since preview. Please refresh and review the merge again.")
            if dest_head_id == src_head_id:
                raise ValueError("Branches are already pointing to the same revision.")

            ancestor = self.find_lowest_common_ancestor(experiment_id, dest_head_id, src_head_id)
            if not ancestor:
                raise ValueError(
                    f"Branches '{dest_branch['name']}' and '{src_branch['name']}' do not share a common history and cannot be merged."
                )

            dest_head = conn.execute("SELECT * FROM prompt_versions WHERE id = ?", (dest_head_id,)).fetchone()
            src_head = conn.execute("SELECT * FROM prompt_versions WHERE id = ?", (src_head_id,)).fetchone()

            raw_fs = resolved_fields.get("few_shot_examples", dest_head["few_shot_examples"])
            few_shots: list[FewShotExample] = []
            if isinstance(raw_fs, str):
                try:
                    raw_fs = json.loads(raw_fs)
                except Exception:
                    raw_fs = []
            if isinstance(raw_fs, list):
                for item in raw_fs:
                    if isinstance(item, dict):
                        few_shots.append(FewShotExample(**item))
                    elif isinstance(item, FewShotExample):
                        few_shots.append(item)

            next_num = self.get_next_version_number(experiment_id)
            default_label = f"Merge branch '{src_branch['name']}' into '{dest_branch['name']}'"
            version_label = custom_label.strip() if custom_label.strip() else default_label

            merge_meta = {
                "source_branch_id": src_branch["id"],
                "source_branch_name": src_branch["name"],
                "source_head_version_id": src_head_id,
                "source_version_number": src_head["version_number"],
                "destination_branch_id": dest_branch["id"],
                "destination_branch_name": dest_branch["name"],
                "destination_head_version_id": dest_head_id,
                "destination_version_number": dest_head["version_number"],
                "ancestor_version_id": ancestor["id"],
                "ancestor_version_number": ancestor["version_number"],
                "merged_at": _now(),
                "is_fast_forward": False,
            }

            merged_pv = PromptVersion(
                id=_new_id(),
                experiment_id=experiment_id,
                branch_id=dest_branch["id"],
                version_number=next_num,
                parent_version_id=dest_head_id,
                parent_2_version_id=src_head_id,
                merge_metadata=merge_meta,
                version_label=version_label,
                system_prompt=resolved_fields.get("system_prompt", dest_head["system_prompt"]),
                user_prompt_template=resolved_fields.get("user_prompt_template", dest_head["user_prompt_template"]),
                technique=PromptingTechnique(resolved_fields.get("technique", dest_head["technique"])),
                output_format=OutputFormat(resolved_fields.get("output_format", dest_head["output_format"])),
                few_shot_examples=few_shots,
                model_name=resolved_fields.get("model_name", dest_head["model_name"]),
                temperature=float(resolved_fields.get("temperature", dest_head["temperature"])),
                max_tokens=int(resolved_fields.get("max_tokens", dest_head["max_tokens"])),
            )

        self.save_prompt_version(merged_pv)
        return {
            "version_id": merged_pv.id,
            "version_number": merged_pv.version_number,
            "is_fast_forward": False,
        }

    # ── Prompt Versions ────────────────────────────────────────────────

    def save_prompt_version(self, pv: PromptVersion) -> str:
        with self._connect() as conn:
            parent_row = None
            if pv.parent_version_id:
                parent_row = conn.execute(
                    "SELECT experiment_id, branch_id FROM prompt_versions WHERE id = ?",
                    (pv.parent_version_id,),
                ).fetchone()
                if not parent_row or parent_row["experiment_id"] != pv.experiment_id:
                    raise ValueError("A revision parent must be an existing version in the same experiment.")
            if pv.parent_2_version_id:
                parent_2_row = conn.execute(
                    "SELECT experiment_id FROM prompt_versions WHERE id = ?",
                    (pv.parent_2_version_id,),
                ).fetchone()
                if not parent_2_row or parent_2_row["experiment_id"] != pv.experiment_id:
                    raise ValueError("A second revision parent must be an existing version in the same experiment.")
            branch = None
            new_main_branch = False
            if pv.branch_id:
                branch = conn.execute(
                    "SELECT * FROM prompt_branches WHERE id = ?", (pv.branch_id,)
                ).fetchone()
                if not branch or branch["experiment_id"] != pv.experiment_id:
                    raise ValueError("Choose a branch from this experiment before saving a revision.")
            else:
                if parent_row:
                    pv.branch_id = parent_row["branch_id"]
                if pv.branch_id:
                    branch = conn.execute(
                        "SELECT * FROM prompt_branches WHERE id = ?", (pv.branch_id,)
                    ).fetchone()
                if not branch:
                    branch = conn.execute(
                        "SELECT * FROM prompt_branches WHERE experiment_id = ? AND name = 'main' COLLATE NOCASE",
                        (pv.experiment_id,),
                    ).fetchone()
                if not branch:
                    pv.branch_id = _new_id()
                    new_main_branch = True
                else:
                    pv.branch_id = branch["id"]
                    if pv.parent_version_id is None and branch["head_version_id"]:
                        pv.parent_version_id = branch["head_version_id"]

            if branch and pv.parent_version_id != branch["head_version_id"]:
                raise ValueError("This branch has moved. Open its latest revision before saving a new one.")
            duplicate = conn.execute(
                "SELECT 1 FROM prompt_versions WHERE experiment_id = ? AND version_number = ?",
                (pv.experiment_id, pv.version_number),
            ).fetchone()
            if duplicate:
                raise ValueError(f"Version number {pv.version_number} already exists in this experiment.")
            conn.execute(
                "INSERT INTO prompt_versions "
                "(id, experiment_id, branch_id, version_number, parent_version_id, parent_2_version_id, "
                "merge_metadata, version_label, system_prompt, user_prompt_template, technique, "
                "few_shot_examples, output_format, variables, model_name, temperature, max_tokens, "
                "is_optimized, optimization_strategy, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pv.id, pv.experiment_id, pv.branch_id, pv.version_number, pv.parent_version_id,
                 pv.parent_2_version_id,
                 json.dumps(pv.merge_metadata) if isinstance(pv.merge_metadata, dict) else (pv.merge_metadata or ""),
                 pv.version_label, pv.system_prompt, pv.user_prompt_template, pv.technique.value,
                 json.dumps([e.model_dump() for e in pv.few_shot_examples]),
                 pv.output_format.value, json.dumps(pv.variables),
                 pv.model_name, pv.temperature, pv.max_tokens,
                 1 if pv.is_optimized else 0, pv.optimization_strategy,
                 pv.created_at),
            )
            now = _now()
            if new_main_branch:
                conn.execute(
                    "INSERT INTO prompt_branches (id, experiment_id, name, head_version_id, base_version_id, description, created_at, updated_at) "
                    "VALUES (?, ?, 'main', ?, ?, '', ?, ?)",
                    (pv.branch_id, pv.experiment_id, pv.id, pv.id, now, now),
                )
            else:
                conn.execute(
                    "UPDATE prompt_branches SET head_version_id = ?, updated_at = ? WHERE id = ?",
                    (pv.id, now, pv.branch_id),
                )
        return pv.id

    def get_prompt_versions(self, experiment_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM prompt_versions WHERE experiment_id = ? ORDER BY version_number",
                (experiment_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def duplicate_prompt_history(self, source_experiment_id: str, target_experiment_id: str):
        """Copy revisions and named branch pointers into a duplicated experiment."""
        with self._connect() as conn:
            versions = conn.execute(
                "SELECT * FROM prompt_versions WHERE experiment_id = ? ORDER BY version_number, created_at",
                (source_experiment_id,),
            ).fetchall()
            branches = conn.execute(
                "SELECT * FROM prompt_branches WHERE experiment_id = ? ORDER BY name COLLATE NOCASE",
                (source_experiment_id,),
            ).fetchall()
            version_ids = {row["id"]: _new_id() for row in versions}
            branch_ids = {row["id"]: _new_id() for row in branches}
            for row in versions:
                conn.execute(
                    "INSERT INTO prompt_versions "
                    "(id, experiment_id, branch_id, version_number, parent_version_id, parent_2_version_id, "
                    "merge_metadata, version_label, system_prompt, user_prompt_template, technique, "
                    "few_shot_examples, output_format, variables, model_name, "
                    "temperature, max_tokens, is_optimized, optimization_strategy, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (version_ids[row["id"]], target_experiment_id,
                     branch_ids.get(row["branch_id"]), row["version_number"],
                     version_ids.get(row["parent_version_id"]),
                     version_ids.get(row["parent_2_version_id"]) if row["parent_2_version_id"] else None,
                     row["merge_metadata"] or "", row["version_label"],
                     row["system_prompt"], row["user_prompt_template"], row["technique"],
                     row["few_shot_examples"], row["output_format"], row["variables"],
                     row["model_name"], row["temperature"], row["max_tokens"],
                     row["is_optimized"], row["optimization_strategy"], row["created_at"]),
                )
            for row in branches:
                conn.execute(
                    "INSERT INTO prompt_branches (id, experiment_id, name, head_version_id, base_version_id, description, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (branch_ids[row["id"]], target_experiment_id, row["name"],
                     version_ids[row["head_version_id"]], version_ids[row["base_version_id"]],
                     row["description"], row["created_at"], row["updated_at"]),
                )

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
            counter_key = f"version_counter:{experiment_id}"
            counter = conn.execute("SELECT value FROM app_meta WHERE key = ?", (counter_key,)).fetchone()
            next_number = max((row["mx"] or 0) + 1, int(counter["value"]) if counter else 1)
            conn.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)", (counter_key, str(next_number + 1)))
            return next_number

    def delete_prompt_version(self, version_id: str):
        with self._connect() as conn:
            version = conn.execute(
                "SELECT experiment_id, parent_version_id FROM prompt_versions WHERE id = ?", (version_id,)
            ).fetchone()
            if not version:
                return
            child = conn.execute(
                "SELECT 1 FROM prompt_versions WHERE parent_version_id = ? OR parent_2_version_id = ? LIMIT 1",
                (version_id, version_id),
            ).fetchone()
            if child:
                raise ValueError("This revision has child revisions and cannot be deleted.")
            branch_refs = conn.execute(
                "SELECT * FROM prompt_branches WHERE head_version_id = ? OR base_version_id = ?",
                (version_id, version_id),
            ).fetchall()
            parent_id = version["parent_version_id"]
            for branch in branch_refs:
                if branch["base_version_id"] == version_id and branch["head_version_id"] != version_id:
                    raise ValueError("This revision is the starting point for a branch and cannot be deleted.")
                if branch["head_version_id"] == version_id:
                    if not parent_id:
                        if branch["name"].lower() == "main" and branch["base_version_id"] == version_id:
                            conn.execute("DELETE FROM prompt_branches WHERE id = ?", (branch["id"],))
                            continue
                        raise ValueError("This revision is a branch starting point. Delete that branch first.")
                    new_base = parent_id if branch["base_version_id"] == version_id else branch["base_version_id"]
                    conn.execute(
                        "UPDATE prompt_branches SET head_version_id = ?, base_version_id = ?, updated_at = ? WHERE id = ?",
                        (parent_id, new_base, _now(), branch["id"]),
                    )
            conn.execute("DELETE FROM evaluation_runs WHERE prompt_version_id = ?", (version_id,))
            exp_id = version["experiment_id"]
            max_row = conn.execute("SELECT MAX(version_number) AS mx FROM prompt_versions WHERE experiment_id = ?", (exp_id,)).fetchone()
            counter_key = f"version_counter:{exp_id}"
            counter = conn.execute("SELECT value FROM app_meta WHERE key = ?", (counter_key,)).fetchone()
            next_number = max((max_row["mx"] or 0) + 1, int(counter["value"]) if counter else 1)
            conn.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)", (counter_key, str(next_number)))
            conn.execute("DELETE FROM evaluation_results WHERE prompt_version_id = ?", (version_id,))
            conn.execute("DELETE FROM optimization_candidates WHERE original_version_id = ?", (version_id,))
            conn.execute("DELETE FROM prompt_versions WHERE id = ?", (version_id,))

    def update_prompt_version(
        self,
        version_id: str,
        version_label: str,
        system_prompt: str,
        user_prompt_template: str,
        technique: str,
        output_format: str,
        model_name: str,
        temperature: float,
        max_tokens: int,
        few_shot_examples: list[dict] | None = None,
        variables: list[str] | None = None,
    ):
        raise ValueError("Prompt versions are immutable; save these values as a new revision.")

    def create_evaluation_run(
        self, experiment_id: str, prompt_version_id: str, method: str,
        weights: dict, config: dict, test_cases: list[dict],
    ) -> str:
        """Persist the complete evaluation context before execution starts."""
        run_id = _new_id()
        snapshot = [{
            "id": tc["id"], "input_data": tc.get("input_data", ""),
            "expected_output": tc.get("expected_output", ""),
            "metadata": tc.get("metadata", {}),
        } for tc in test_cases]
        signature_data = {"method": method, "weights": weights, "config": config, "test_cases": snapshot}
        signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode("utf-8")).hexdigest()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO evaluation_runs (id, experiment_id, prompt_version_id, method, weights, config, test_cases_snapshot, signature, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)",
                (run_id, experiment_id, prompt_version_id, method, json.dumps(weights, sort_keys=True),
                 json.dumps(config, sort_keys=True), json.dumps(snapshot, sort_keys=True), signature, _now()),
            )
        return run_id

    def update_evaluation_run_status(self, run_id: str, status: str):
        with self._connect() as conn:
            conn.execute("UPDATE evaluation_runs SET status = ? WHERE id = ?", (status, run_id))

    def get_evaluation_runs(self, experiment_id: str, prompt_version_id: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if prompt_version_id:
                rows = conn.execute(
                    "SELECT * FROM evaluation_runs WHERE experiment_id = ? AND prompt_version_id = ? ORDER BY created_at DESC",
                    (experiment_id, prompt_version_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM evaluation_runs WHERE experiment_id = ? ORDER BY created_at DESC",
                    (experiment_id,),
                ).fetchall()
            return [dict(row) for row in rows]

    def get_comparable_evaluation_run_pairs(
        self, experiment_id: str, version_a_id: str, version_b_id: str,
    ) -> list[tuple[dict, dict]]:
        """Return completed run pairs with identical settings and test snapshots."""
        runs_a = self.get_evaluation_runs(experiment_id, version_a_id)
        runs_b = self.get_evaluation_runs(experiment_id, version_b_id)
        return [
            (a, b) for a in runs_a for b in runs_b
            if a["status"] == "done" and b["status"] == "done"
            and a["signature"] and a["signature"] == b["signature"]
        ]

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
                "(id, test_case_id, prompt_version_id, experiment_id, evaluation_run_id, input_data_snapshot, expected_output_snapshot, generated_output, "
                "criterion_scores, overall_score, weaknesses, suggestions, "
                "evaluation_method, is_reference_verified, execution_status, "
                "error_message, latency_ms, tokens_used, cost_estimate, is_demo, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (er.id, er.test_case_id, er.prompt_version_id, er.experiment_id,
                 er.evaluation_run_id, er.input_data_snapshot, er.expected_output_snapshot,
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

    def save_evaluation_results_bulk(self, results: list[EvaluationResult]):
        """Save multiple evaluation results inside a single transactional commit."""
        if not results:
            return
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO evaluation_results "
                "(id, test_case_id, prompt_version_id, experiment_id, evaluation_run_id, input_data_snapshot, expected_output_snapshot, generated_output, "
                "criterion_scores, overall_score, weaknesses, suggestions, "
                "evaluation_method, is_reference_verified, execution_status, "
                "error_message, latency_ms, tokens_used, cost_estimate, is_demo, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(er.id, er.test_case_id, er.prompt_version_id, er.experiment_id,
                  er.evaluation_run_id, er.input_data_snapshot, er.expected_output_snapshot,
                  er.generated_output,
                  json.dumps([s.model_dump() for s in er.criterion_scores]),
                  er.overall_score,
                  json.dumps(er.weaknesses), json.dumps(er.suggestions),
                  er.evaluation_method.value,
                  1 if er.is_reference_verified else 0,
                  er.execution_status.value, er.error_message,
                  er.latency_ms, er.tokens_used, er.cost_estimate,
                  1 if er.is_demo else 0, er.created_at) for er in results],
            )

    def get_evaluation_results(
        self, experiment_id: str, prompt_version_id: Optional[str] = None,
        evaluation_run_id: Optional[str] = None,
    ) -> list[dict]:
        with self._connect() as conn:
            if evaluation_run_id:
                rows = conn.execute(
                    "SELECT * FROM evaluation_results WHERE experiment_id = ? AND evaluation_run_id = ? ORDER BY created_at",
                    (experiment_id, evaluation_run_id),
                ).fetchall()
            elif prompt_version_id:
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

    def delete_prompt_template(self, template_id: str, allow_builtin: bool = False):
        with self._connect() as conn:
            if allow_builtin:
                conn.execute("DELETE FROM prompt_library WHERE id = ?", (template_id,))
            else:
                conn.execute("DELETE FROM prompt_library WHERE id = ? AND is_builtin = 0", (template_id,))

    def get_meta(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_meta(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
                (key, value),
            )

    def clear_all_experiments(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM evaluation_runs")
            conn.execute("DELETE FROM evaluation_results")
            conn.execute("DELETE FROM optimization_candidates")
            conn.execute("DELETE FROM test_cases")
            conn.execute("DELETE FROM prompt_branches")
            conn.execute("DELETE FROM prompt_versions")
            conn.execute("DELETE FROM experiments")

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
