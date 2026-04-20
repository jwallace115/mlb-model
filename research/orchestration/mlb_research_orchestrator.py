"""
MLB Research Orchestrator — Frozen Foundation Enforcement Layer
Rebuilt 2026-04-19 from frozen foundation package after session-loss event.
"""
import json, csv, os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ORCH_DIR = Path(__file__).resolve().parent
_FOUNDATION_ROOT = _REPO_ROOT / "research" / "engine_foundation" / "mlb_engine_v1_foundation"

class Orchestrator:
    def __init__(self, config_path=None):
        self._config_path = config_path or (_ORCH_DIR / "mlb_research_orchestration_config.json")
        self.config = self._load_json(self._config_path)
        self.registry = self.load_foundation_registry()
        self.included = self.load_included_artifacts()
        self.excluded = self.load_excluded_artifacts()
        self.caveats = self.load_caveats()

    def _load_json(self, path):
        with open(path) as f:
            return json.load(f)

    def _load_csv(self, path):
        with open(path, newline="") as f:
            return list(csv.DictReader(f))

    def load_foundation_registry(self):
        return self._load_json(_FOUNDATION_ROOT / "MLB_ENGINE_V1_FOUNDATION_REGISTRY.json")

    def load_included_artifacts(self):
        return self._load_csv(_FOUNDATION_ROOT / "MLB_ENGINE_V1_FOUNDATION_INCLUDED_ARTIFACTS.csv")

    def load_excluded_artifacts(self):
        return self._load_csv(_FOUNDATION_ROOT / "MLB_ENGINE_V1_FOUNDATION_EXCLUDED_ARTIFACTS.csv")

    def load_caveats(self):
        data = self._load_json(_FOUNDATION_ROOT / "MLB_ENGINE_V1_FOUNDATION_CAVEATS.json")
        return data.get("caveats", [])

    def get_real_current_base_object(self):
        return self.registry["real_current_base_object"]

    def get_included_families(self):
        return list(self.registry["included_artifact_families"])

    def get_excluded_families(self):
        return list(self.registry["excluded_artifact_families"])

    def get_included_paths(self):
        return dict(self.registry["included_artifact_paths"])

    def validate_requested_paths(self, requested_paths):
        approved = set(self.registry["included_artifact_paths"].values())
        for row in self.included:
            pp = row.get("package_path", "")
            if pp and "REF_ONLY" not in pp:
                approved.add(pp)
        violations = []
        for p in requested_paths:
            rel = p.replace(str(_REPO_ROOT) + "/", "").lstrip("/")
            if rel not in approved:
                violations.append({"path": rel, "reason": "NOT_IN_INCLUDED_MANIFEST"})
        return (len(violations) == 0, violations)

    def validate_requested_artifact_families(self, requested_families):
        included = set(self.get_included_families())
        excluded = set(self.get_excluded_families())
        violations = []
        for fam in requested_families:
            if fam in excluded:
                violations.append({"family": fam, "reason": "EXPLICITLY_EXCLUDED"})
            elif fam not in included:
                violations.append({"family": fam, "reason": "NOT_IN_INCLUDED_MANIFEST"})
        return (len(violations) == 0, violations)

    def enforce_default_deny_for_nonpackage_paths(self, paths):
        is_valid, violations = self.validate_requested_paths(paths)
        if not is_valid:
            return self.render_hard_stop_message(
                f"DEFAULT_DENY: {len(violations)} path(s) rejected. Violations: {violations}")
        return None

    def get_required_caveats_for_artifacts(self, artifact_families):
        applicable = []
        for c in self.caveats:
            if c["artifact_family"] in artifact_families or c["artifact_family"] == "governance_layer":
                applicable.append(c)
        return applicable

    def get_workflow_template(self, workflow_name):
        templates = self._load_json(_ORCH_DIR / "mlb_research_workflow_templates.json")
        for t in templates.get("templates", []):
            if t["workflow_name"] == workflow_name:
                return t
        return None

    def validate_split_request(self, split_definition):
        expected = {"discovery": "2022-2023", "validation": "2024", "OOS": "2025"}
        issues = []
        for stage, expected_val in expected.items():
            actual = split_definition.get(stage)
            if actual != expected_val:
                issues.append(f"{stage}: expected '{expected_val}', got '{actual}'")
        return (len(issues) == 0, issues)

    def create_branch_status_stub(self, branch_name, branch_type, parent_branch=None):
        return {
            "branch_name": branch_name, "branch_type": branch_type,
            "parent_branch": parent_branch, "current_status": "OPEN",
            "opening_date": None, "last_updated": None, "advancement_type": None,
            "data_source_scope": "MLB_ENGINE_V1_FOUNDATION",
            "base_object_used": self.registry["real_current_base_object"]["frozen_copy"],
            "artifact_families_used": [], "caveats_applied": [],
            "provenance_type": None, "notes": None,
        }

    def build_task_opening_confirmation(self, task_name, requested_artifacts):
        fam_valid, fam_violations = self.validate_requested_artifact_families(requested_artifacts)
        caveats = self.get_required_caveats_for_artifacts(requested_artifacts)
        base = self.get_real_current_base_object()
        return {
            "task_name": task_name, "base_object": base["name"],
            "base_object_path": base["frozen_copy"],
            "requested_artifacts_valid": fam_valid, "violations": fam_violations,
            "required_caveats": [{"id": c["id"], "text": c["text"]} for c in caveats],
            "approved": fam_valid,
            "hard_stop": None if fam_valid else self.render_hard_stop_message(
                f"Task '{task_name}' blocked: {fam_violations}"),
        }

    def render_hard_stop_message(self, reason):
        return (
            "═══ HARD STOP ═══\n"
            f"MLB Orchestration Layer — Default Deny Triggered\n"
            f"Reason: {reason}\n"
            f"Resolution: Use only artifacts listed in the frozen foundation package.\n"
            f"Package: {self.config['foundation_package_root']}\n"
            "═════════════════")

if __name__ == "__main__":
    orch = Orchestrator()
    base = orch.get_real_current_base_object()
    print(f"MLB Research Orchestrator — Active")
    print(f"Foundation: {orch.config['foundation_package_root']}")
    print(f"Base object: {base['name']} ({base['rows']}x{base['columns']})")
    print(f"Included families: {len(orch.get_included_families())}")
    print(f"Excluded families: {len(orch.get_excluded_families())}")
    print(f"Caveats: {len(orch.caveats)}")
    print(f"Default deny: {orch.config['default_deny']}")
    print(f"Repo-wide fallback: {orch.config['allow_repo_wide_fallback']}")
