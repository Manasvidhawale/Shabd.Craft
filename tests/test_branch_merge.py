"""
Shabd.Craft — Tests: Prompt Branch 3-Way Merge Functionality
Tests for Lowest Common Ancestor (LCA), 3-way merge computation, conflict resolution,
fast-forward merges, immutable merge commits, and DAG lineage protection.
"""

import json
import sqlite3
import pytest
from src.database import Database
from src.experiment_service import duplicate_experiment
from src.schemas import (
    Experiment,
    PromptVersion,
    FewShotExample,
    PromptingTechnique,
    OutputFormat,
)


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test_merge.db")
    return Database(db_path)


@pytest.fixture
def base_experiment(db):
    exp = Experiment(name="Branching & Merging Test")
    exp_id = db.create_experiment(exp)

    # Base version v1 on main branch
    v1 = PromptVersion(
        experiment_id=exp_id,
        version_number=1,
        version_label="Base Version v1",
        system_prompt="Base system prompt",
        user_prompt_template="Input: {input}",
        technique=PromptingTechnique.ZERO_SHOT,
        output_format=OutputFormat.TEXT,
        model_name="gemini-1.5-flash",
        temperature=0.7,
        max_tokens=1000,
    )
    v1_id = db.save_prompt_version(v1)
    main_branch = db.get_prompt_branches(exp_id)[0]
    return exp_id, main_branch, v1_id


class TestLowestCommonAncestor:
    def test_lca_linear_history(self, db, base_experiment):
        exp_id, main_branch, v1_id = base_experiment
        v2 = PromptVersion(
            experiment_id=exp_id,
            branch_id=main_branch["id"],
            version_number=2,
            version_label="v2",
            parent_version_id=v1_id,
            system_prompt="v2 system",
            user_prompt_template="Input: {input}",
        )
        v2_id = db.save_prompt_version(v2)

        v3 = PromptVersion(
            experiment_id=exp_id,
            branch_id=main_branch["id"],
            version_number=3,
            version_label="v3",
            parent_version_id=v2_id,
            system_prompt="v3 system",
            user_prompt_template="Input: {input}",
        )
        v3_id = db.save_prompt_version(v3)

        # LCA of v1 and v3 is v1
        lca13 = db.find_lowest_common_ancestor(exp_id, v1_id, v3_id)
        assert lca13 is not None
        assert lca13["id"] == v1_id

        # LCA of v2 and v3 is v2
        lca23 = db.find_lowest_common_ancestor(exp_id, v2_id, v3_id)
        assert lca23 is not None
        assert lca23["id"] == v2_id

    def test_lca_divergent_branches(self, db, base_experiment):
        exp_id, main_branch, v1_id = base_experiment

        # Branch feature-a
        b_a_id = db.create_prompt_branch(exp_id, "feature-a", v1_id)
        v_a = PromptVersion(
            experiment_id=exp_id,
            branch_id=b_a_id,
            version_number=2,
            version_label="feature a head",
            parent_version_id=v1_id,
            system_prompt="feature a system",
            user_prompt_template="{input}",
        )
        va_id = db.save_prompt_version(v_a)

        # Branch feature-b
        b_b_id = db.create_prompt_branch(exp_id, "feature-b", v1_id)
        v_b = PromptVersion(
            experiment_id=exp_id,
            branch_id=b_b_id,
            version_number=3,
            version_label="feature b head",
            parent_version_id=v1_id,
            system_prompt="feature b system",
            user_prompt_template="{input}",
        )
        vb_id = db.save_prompt_version(v_b)

        lca = db.find_lowest_common_ancestor(exp_id, va_id, vb_id)
        assert lca is not None
        assert lca["id"] == v1_id

    def test_lca_disjoint_returns_none(self, db):
        exp1 = Experiment(name="Exp 1")
        exp1_id = db.create_experiment(exp1)
        v1 = PromptVersion(experiment_id=exp1_id, version_number=1, version_label="v1", system_prompt="s1", user_prompt_template="u1")
        v1_id = db.save_prompt_version(v1)

        exp2 = Experiment(name="Exp 2")
        exp2_id = db.create_experiment(exp2)
        v2 = PromptVersion(experiment_id=exp2_id, version_number=1, version_label="v2", system_prompt="s2", user_prompt_template="u2")
        v2_id = db.save_prompt_version(v2)

        assert db.find_lowest_common_ancestor(exp1_id, v1_id, v2_id) is None


class TestThreeWayMergeComputation:
    def test_clean_non_overlapping_changes(self, db):
        ancestor = {
            "id": "anc",
            "system_prompt": "Base system",
            "user_prompt_template": "Base user: {input}",
            "technique": "zero_shot",
            "output_format": "text",
            "few_shot_examples": "[]",
            "model_name": "gemini-1.5-flash",
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        # Dest modified system prompt only
        dest = dict(ancestor, system_prompt="Updated system on dest")
        # Source modified temperature and model_name only
        src = dict(ancestor, temperature=0.2, model_name="gemini-1.5-pro")

        result = db.compute_three_way_merge(ancestor, dest, src)
        assert result["has_conflicts"] is False
        assert len(result["conflicts"]) == 0
        assert "system_prompt" in result["auto_merged"]
        assert result["fields"]["system_prompt"]["status"] == "auto_dest"
        assert result["fields"]["temperature"]["status"] == "auto_source"
        assert result["fields"]["temperature"]["proposed"] == 0.2
        assert result["fields"]["model_name"]["status"] == "auto_source"
        assert result["fields"]["model_name"]["proposed"] == "gemini-1.5-pro"
        assert result["fields"]["user_prompt_template"]["status"] == "unchanged"

    def test_detect_conflict(self, db):
        ancestor = {
            "id": "anc",
            "system_prompt": "Base system",
            "user_prompt_template": "Base user: {input}",
            "technique": "zero_shot",
            "output_format": "text",
            "few_shot_examples": "[]",
            "model_name": "gemini-1.5-flash",
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        # Both modified system_prompt differently
        dest = dict(ancestor, system_prompt="Dest tone: formal")
        src = dict(ancestor, system_prompt="Source tone: concise")

        result = db.compute_three_way_merge(ancestor, dest, src)
        assert result["has_conflicts"] is True
        assert "system_prompt" in result["conflicts"]
        assert result["fields"]["system_prompt"]["status"] == "conflict"
        assert result["fields"]["system_prompt"]["is_conflict"] is True
        assert result["fields"]["system_prompt"]["destination"] == "Dest tone: formal"
        assert result["fields"]["system_prompt"]["source"] == "Source tone: concise"

    def test_identical_changes_on_both_branches(self, db):
        ancestor = {
            "id": "anc",
            "system_prompt": "Base system",
            "user_prompt_template": "Base user: {input}",
            "technique": "zero_shot",
            "output_format": "text",
            "few_shot_examples": "[]",
            "model_name": "gemini-1.5-flash",
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        # Both modified model_name to the same value
        dest = dict(ancestor, model_name="gpt-4o")
        src = dict(ancestor, model_name="gpt-4o")

        result = db.compute_three_way_merge(ancestor, dest, src)
        assert result["has_conflicts"] is False
        assert result["fields"]["model_name"]["status"] == "auto_same"
        assert result["fields"]["model_name"]["proposed"] == "gpt-4o"


class TestFastForwardMerge:
    def test_successful_fast_forward(self, db, base_experiment):
        exp_id, main_branch, v1_id = base_experiment

        # Create experiment branch from v1
        branch_id = db.create_prompt_branch(exp_id, "fast-track", v1_id)
        # Add v2 to fast-track branch
        v2 = PromptVersion(
            experiment_id=exp_id,
            branch_id=branch_id,
            version_number=2,
            version_label="v2 on fast-track",
            parent_version_id=v1_id,
            system_prompt="Advanced prompt",
            user_prompt_template="{input}",
        )
        v2_id = db.save_prompt_version(v2)

        # Fast forward main to fast-track
        res = db.execute_fast_forward_merge(
            exp_id,
            dest_branch_id=main_branch["id"],
            source_branch_id=branch_id,
            expected_dest_head_id=v1_id,
            expected_source_head_id=v2_id,
        )
        assert res["is_fast_forward"] is True
        assert res["version_id"] == v2_id

        # Verify main head has moved to v2
        updated_main = db.get_prompt_branch(main_branch["id"])
        assert updated_main["head_version_id"] == v2_id

    def test_fast_forward_fails_if_dest_diverged(self, db, base_experiment):
        exp_id, main_branch, v1_id = base_experiment

        # Advance main to v2
        v2 = PromptVersion(
            experiment_id=exp_id,
            branch_id=main_branch["id"],
            version_number=2,
            version_label="v2 main",
            parent_version_id=v1_id,
            system_prompt="Main updated",
            user_prompt_template="{input}",
        )
        v2_id = db.save_prompt_version(v2)

        # Create branch from v1 and advance it to v3
        branch_id = db.create_prompt_branch(exp_id, "other-branch", v1_id)
        v3 = PromptVersion(
            experiment_id=exp_id,
            branch_id=branch_id,
            version_number=3,
            version_label="v3 other",
            parent_version_id=v1_id,
            system_prompt="Other updated",
            user_prompt_template="{input}",
        )
        v3_id = db.save_prompt_version(v3)

        with pytest.raises(ValueError, match="Fast-forward merge not possible"):
            db.execute_fast_forward_merge(exp_id, main_branch["id"], branch_id)

    def test_fast_forward_fails_on_stale_dest_head(self, db, base_experiment):
        exp_id, main_branch, v1_id = base_experiment
        branch_id = db.create_prompt_branch(exp_id, "feature", v1_id)
        v2 = PromptVersion(
            experiment_id=exp_id,
            branch_id=branch_id,
            version_number=2,
            version_label="v2",
            parent_version_id=v1_id,
            system_prompt="v2",
            user_prompt_template="{input}",
        )
        v2_id = db.save_prompt_version(v2)

        with pytest.raises(ValueError, match="Destination branch has been updated"):
            db.execute_fast_forward_merge(
                exp_id,
                main_branch["id"],
                branch_id,
                expected_dest_head_id="wrong_or_stale_id",
            )


class TestBranchMergeExecution:
    def test_execute_three_way_merge(self, db, base_experiment):
        exp_id, main_branch, v1_id = base_experiment

        # Destination (main) advances to v2
        v2 = PromptVersion(
            experiment_id=exp_id,
            branch_id=main_branch["id"],
            version_number=2,
            version_label="v2 main",
            parent_version_id=v1_id,
            system_prompt="Dest system prompt",
            user_prompt_template="Input: {input}",
        )
        v2_id = db.save_prompt_version(v2)

        # Source branch advances to v3
        src_branch_id = db.create_prompt_branch(exp_id, "feature-clean", v1_id)
        v3 = PromptVersion(
            experiment_id=exp_id,
            branch_id=src_branch_id,
            version_number=3,
            version_label="v3 feature",
            parent_version_id=v1_id,
            system_prompt="Base system prompt",
            user_prompt_template="Enhanced: {input}",
            temperature=0.3,
        )
        v3_id = db.save_prompt_version(v3)

        # Compute merge
        ancestor = db.find_lowest_common_ancestor(exp_id, v2_id, v3_id)
        dest_ver = db.get_prompt_version(v2_id)
        src_ver = db.get_prompt_version(v3_id)
        analysis = db.compute_three_way_merge(ancestor, dest_ver, src_ver)

        resolved_fields = {
            f: info["proposed"] for f, info in analysis["fields"].items()
        }

        # Execute merge
        res = db.execute_branch_merge(
            experiment_id=exp_id,
            dest_branch_id=main_branch["id"],
            source_branch_id=src_branch_id,
            resolved_fields=resolved_fields,
            custom_label="Merge feature-clean into main",
            expected_dest_head_id=v2_id,
            expected_source_head_id=v3_id,
        )

        assert res["is_fast_forward"] is False
        new_ver_id = res["version_id"]

        # Verify merge version created with both parents
        merged_ver = db.get_prompt_version(new_ver_id)
        assert merged_ver["parent_version_id"] == v2_id
        assert merged_ver["parent_2_version_id"] == v3_id
        assert merged_ver["version_number"] == 4
        assert merged_ver["system_prompt"] == "Dest system prompt"
        assert merged_ver["user_prompt_template"] == "Enhanced: {input}"
        assert merged_ver["temperature"] == 0.3

        # Verify merge metadata
        meta = json.loads(merged_ver["merge_metadata"])
        assert meta["source_branch_name"] == "feature-clean"
        assert meta["destination_branch_name"] == "main"
        assert meta["ancestor_version_id"] == v1_id

        # Destination branch head moved to v4
        updated_main = db.get_prompt_branch(main_branch["id"])
        assert updated_main["head_version_id"] == new_ver_id

        # Source branch head is NOT overwritten
        updated_src = db.get_prompt_branch(src_branch_id)
        assert updated_src["head_version_id"] == v3_id

    def test_merge_fails_on_stale_source_head(self, db, base_experiment):
        exp_id, main_branch, v1_id = base_experiment
        src_branch_id = db.create_prompt_branch(exp_id, "feature", v1_id)

        v2 = PromptVersion(
            experiment_id=exp_id,
            branch_id=main_branch["id"],
            version_number=2,
            version_label="v2",
            parent_version_id=v1_id,
            system_prompt="v2",
            user_prompt_template="{input}",
        )
        v2_id = db.save_prompt_version(v2)

        v3 = PromptVersion(
            experiment_id=exp_id,
            branch_id=src_branch_id,
            version_number=3,
            version_label="v3",
            parent_version_id=v1_id,
            system_prompt="v3",
            user_prompt_template="{input}",
        )
        v3_id = db.save_prompt_version(v3)

        with pytest.raises(ValueError, match="Source branch has been updated"):
            db.execute_branch_merge(
                experiment_id=exp_id,
                dest_branch_id=main_branch["id"],
                source_branch_id=src_branch_id,
                resolved_fields={},
                expected_dest_head_id=v2_id,
                expected_source_head_id="stale_v3_head",
            )

    def test_prevent_delete_protected_merge_parents(self, db, base_experiment):
        exp_id, main_branch, v1_id = base_experiment

        v2 = PromptVersion(
            experiment_id=exp_id,
            branch_id=main_branch["id"],
            version_number=2,
            version_label="v2",
            parent_version_id=v1_id,
            system_prompt="v2",
            user_prompt_template="{input}",
        )
        v2_id = db.save_prompt_version(v2)

        src_b_id = db.create_prompt_branch(exp_id, "feat", v1_id)
        v3 = PromptVersion(
            experiment_id=exp_id,
            branch_id=src_b_id,
            version_number=3,
            version_label="v3",
            parent_version_id=v1_id,
            system_prompt="v3",
            user_prompt_template="{input}",
        )
        v3_id = db.save_prompt_version(v3)

        res = db.execute_branch_merge(
            experiment_id=exp_id,
            dest_branch_id=main_branch["id"],
            source_branch_id=src_b_id,
            resolved_fields={},
        )
        merge_ver_id = res["version_id"]

        # Deleting parent 1 (v2) must fail
        with pytest.raises(ValueError, match="child revisions"):
            db.delete_prompt_version(v2_id)

        # Deleting parent 2 (v3) must also fail because it is parent_2_version_id of merge_ver
        with pytest.raises(ValueError, match="child revisions"):
            db.delete_prompt_version(v3_id)

    def test_duplicate_experiment_preserves_merge_metadata(self, db, base_experiment):
        exp_id, main_branch, v1_id = base_experiment

        v2 = PromptVersion(
            experiment_id=exp_id,
            branch_id=main_branch["id"],
            version_number=2,
            version_label="v2",
            parent_version_id=v1_id,
            system_prompt="v2",
            user_prompt_template="{input}",
        )
        v2_id = db.save_prompt_version(v2)

        src_b_id = db.create_prompt_branch(exp_id, "feat", v1_id)
        v3 = PromptVersion(
            experiment_id=exp_id,
            branch_id=src_b_id,
            version_number=3,
            version_label="v3",
            parent_version_id=v1_id,
            system_prompt="v3",
            user_prompt_template="{input}",
        )
        v3_id = db.save_prompt_version(v3)

        res = db.execute_branch_merge(
            experiment_id=exp_id,
            dest_branch_id=main_branch["id"],
            source_branch_id=src_b_id,
            resolved_fields={"system_prompt": "Merged System"},
        )
        merge_id = res["version_id"]

        # Duplicate experiment
        dup_exp_id = duplicate_experiment(db, exp_id, "Duplicated With Merges")
        dup_versions = db.get_prompt_versions(dup_exp_id)
        dup_merge_ver = next(v for v in dup_versions if v["version_number"] == 4)

        assert dup_merge_ver["parent_version_id"] is not None
        assert dup_merge_ver["parent_2_version_id"] is not None
        assert "Merge branch" in dup_merge_ver["version_label"]
        assert dup_merge_ver["merge_metadata"] != ""
