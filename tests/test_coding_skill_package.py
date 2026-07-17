from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills"
BUILDER_PATH = ROOT / "tools" / "build_coding_agent_skills.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_coding_agent_skills", BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_coding_agent_skill_package_is_complete_and_consistent() -> None:
    builder = load_builder()
    manifest = builder.load_manifest(PACKAGE)

    assert len(manifest) == 98
    assert builder.validate(PACKAGE, manifest) == []
    assert sum(1 for item in manifest if item["virtual"]) == 1
    assert next(item for item in manifest if item["node"] == "PHASE_2_TASK_LOOP")["virtual"] is True
    assert next(item for item in manifest if item["node"] == "END")["terminal"] is True

    kinds = Counter(str(item["kind"]) for item in manifest)
    assert kinds == {
        "decision": 35,
        "control": 16,
        "state": 16,
        "action": 15,
        "verification": 14,
        "delivery": 2,
    }


def test_coding_agent_manifest_is_json_round_trip_stable() -> None:
    manifest_path = PACKAGE / "manifest.json"
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    assert rendered == manifest_path.read_text(encoding="utf-8")
