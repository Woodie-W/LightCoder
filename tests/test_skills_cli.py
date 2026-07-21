from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

from lightcoder.cli import main, parse_duration
from lightcoder.skills import SkillRegistry


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_coding_agent_skills.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("skill_builder", BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compact_skill_package_is_complete_and_generic(
    tmp_path: Path, skills_root: Path
) -> None:
    builder = load_builder()
    manifest = builder.load_manifest(skills_root)
    assert len(manifest["skills"]) == 14
    assert builder.validate(skills_root, manifest) == []
    registry = SkillRegistry(skills_root)
    assert len(registry.metadata()) == 14
    output = tmp_path / "skills.zip"
    builder.build_zip(skills_root, output)
    with zipfile.ZipFile(output) as archive:
        assert len(archive.namelist()) == 15
        assert "skills/manifest.json" in archive.namelist()


def test_cli_duration_and_state_commands(tmp_path: Path, capsys) -> None:
    assert parse_duration("4h") == 14_400
    assert parse_duration("30m") == 1_800
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    assert main(["list", "--workspace", str(workspace)]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_cli_adopts_existing_evaluator_in_one_command(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "score.txt").write_text("0.75\n", encoding="utf-8")
    (workspace / "evaluate.py").write_text(
        """import sys
from pathlib import Path
print(f"partial={Path(sys.argv[1]).read_text().strip()}")
""",
        encoding="utf-8",
    )
    store = tmp_path / "store"

    result = main(
        [
            "eval",
            "--workspace",
            str(workspace),
            "--store",
            str(store),
            "--adopt",
            "evaluate.py",
            "--primary",
            "partial",
            "--",
            str(workspace / "score.txt"),
        ]
    )

    assert result == 0
    assert "partial=0.75" in capsys.readouterr().out
