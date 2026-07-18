from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class SkillError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    name: str
    description: str
    path: Path


class SkillRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._skills: dict[str, SkillMetadata] = {}
        self.discover()

    def discover(self) -> list[SkillMetadata]:
        skills: dict[str, SkillMetadata] = {}
        if not self.root.is_dir():
            self._skills = skills
            return []
        for path in sorted(self.root.glob("*/SKILL.md")):
            header = self._frontmatter(path.read_text(encoding="utf-8"))
            name = header.get("name", path.parent.name).strip()
            description = header.get("description", "").strip()
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
                raise SkillError(f"invalid skill name in {path}: {name}")
            if name in skills:
                raise SkillError(f"duplicate skill: {name}")
            if not description:
                raise SkillError(f"skill description is required: {path}")
            skills[name] = SkillMetadata(name, description, path)
        self._skills = skills
        return list(skills.values())

    def metadata(self) -> list[SkillMetadata]:
        return list(self._skills.values())

    def catalog(self) -> str:
        return "\n".join(
            f"- {item.name}: {item.description}" for item in self.metadata()
        )

    def load(self, name: str) -> str:
        try:
            path = self._skills[name].path
        except KeyError as error:
            raise SkillError(f"unknown skill: {name}") from error
        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n"):
            closing = text.find("\n---\n", 4)
            if closing >= 0:
                text = text[closing + 5 :]
        return text.strip()

    @staticmethod
    def _frontmatter(text: str) -> dict[str, str]:
        if not text.startswith("---\n"):
            return {}
        closing = text.find("\n---\n", 4)
        if closing < 0:
            return {}
        result: dict[str, str] = {}
        for line in text[4:closing].splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip("\"'")
        return result
