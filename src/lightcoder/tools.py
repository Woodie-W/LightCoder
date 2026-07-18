from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import tarfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import new_id, utc_now
from .store import StateStore


class ToolPolicyError(ValueError):
    pass


@dataclass(slots=True)
class ToolResult:
    tool: str
    call_id: str
    success: bool
    duration_seconds: float
    output: str = ""
    raw_log: str = ""
    affected_paths: list[str] = field(default_factory=list)
    exit_code: int | None = None
    background_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkspaceTools:
    def __init__(
        self,
        workspace: Path,
        store: StateStore,
        *,
        protected_paths: list[Path] | None = None,
        max_context_chars: int = 20_000,
    ) -> None:
        self.workspace = workspace.resolve()
        self.store = store
        self.max_context_chars = max(1_000, max_context_chars)
        protected = [path.resolve() for path in protected_paths or []]
        try:
            store.root.relative_to(self.workspace)
            protected.append(store.root)
        except ValueError:
            pass
        self.protected_paths = protected

    def resolve_path(self, value: str, *, write: bool = False) -> Path:
        candidate = (self.workspace / value).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as error:
            raise ToolPolicyError(f"path escapes workspace: {value}") from error
        if write and any(
            candidate == root or root in candidate.parents
            for root in self.protected_paths
        ):
            raise ToolPolicyError(f"path is protected: {value}")
        return candidate

    def read(
        self, path: str, *, start_line: int = 1, max_lines: int = 400
    ) -> ToolResult:
        started = time.monotonic()
        call_id = new_id("read")
        try:
            target = self.resolve_path(path)
            if not target.is_file():
                raise FileNotFoundError(path)
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
            first = max(0, start_line - 1)
            selected = lines[first : first + max(1, min(max_lines, 2_000))]
            output = "\n".join(
                f"{index}: {line}" for index, line in enumerate(selected, first + 1)
            )
            if first + len(selected) < len(lines):
                output += f"\n... truncated; {len(lines)} total lines"
            return ToolResult(
                "read", call_id, True, time.monotonic() - started, output=output
            )
        except (OSError, ToolPolicyError) as error:
            return ToolResult(
                "read", call_id, False, time.monotonic() - started, output=str(error)
            )

    def write(self, path: str, content: str) -> ToolResult:
        started = time.monotonic()
        call_id = new_id("write")
        try:
            target = self.resolve_path(path, write=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            relative = str(target.relative_to(self.workspace))
            return ToolResult(
                "write",
                call_id,
                True,
                time.monotonic() - started,
                output=f"wrote {len(content.encode('utf-8'))} bytes to {relative}",
                affected_paths=[relative],
            )
        except (OSError, ToolPolicyError) as error:
            return ToolResult(
                "write", call_id, False, time.monotonic() - started, output=str(error)
            )

    def compact(self, value: str) -> str:
        if len(value) <= self.max_context_chars:
            return value
        half = self.max_context_chars // 2
        omitted = len(value) - (half * 2)
        return f"{value[:half]}\n... {omitted} characters omitted; see raw log ...\n{value[-half:]}"

    def workspace_revision(self) -> str:
        hasher = hashlib.sha256()
        git = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
                "--",
                ".",
                ":(exclude).lightcoder",
            ],
            cwd=self.workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if git.returncode == 0:
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.workspace,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            ).stdout.strip()
            hasher.update(head.encode())
            hasher.update(git.stdout)
            diff = subprocess.run(
                ["git", "diff", "--binary", "HEAD", "--", ".", ":(exclude).lightcoder"],
                cwd=self.workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            hasher.update(diff.stdout)
            for entry in git.stdout.split(b"\0"):
                if not entry.startswith(b"?? "):
                    continue
                path = entry[3:].decode(errors="surrogateescape")
                target = self.workspace / path
                if target.is_file() and not self._is_runtime_path(target):
                    hasher.update(path.encode(errors="surrogateescape"))
                    try:
                        hasher.update(target.read_bytes())
                    except OSError:
                        pass
            return f"sha256:{hasher.hexdigest()}"

        for target in sorted(
            path for path in self.workspace.rglob("*") if path.is_file()
        ):
            if self._is_runtime_path(target):
                continue
            relative = target.relative_to(self.workspace)
            hasher.update(str(relative).encode())
            try:
                hasher.update(target.read_bytes())
            except OSError:
                continue
        return f"sha256:{hasher.hexdigest()}"

    def changed_files(self) -> list[str]:
        result = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
                "--",
                ".",
                ":(exclude).lightcoder",
            ],
            cwd=self.workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode != 0:
            return sorted(
                str(path.relative_to(self.workspace))
                for path in self.workspace.rglob("*")
                if path.is_file() and not self._is_runtime_path(path)
            )
        records = result.stdout.split(b"\0")
        paths: list[str] = []
        skip_rename_source = False
        for record in records:
            if not record:
                continue
            if skip_rename_source:
                skip_rename_source = False
                continue
            text = record.decode("utf-8", errors="surrogateescape")
            if len(text) <= 3:
                continue
            paths.append(text[3:])
            if text[0] in {"R", "C"} or text[1] in {"R", "C"}:
                skip_rename_source = True
        return sorted(set(paths))

    def git_head(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def create_checkpoint_snapshot(self, checkpoint_id: str, paths: list[str]) -> str:
        snapshot = self.store.checkpoints_dir / f"{checkpoint_id}.tar.gz"
        included: set[str] = set()
        with tarfile.open(snapshot, "w:gz") as archive:
            for value in paths:
                try:
                    target = self.resolve_path(value)
                    relative = str(target.relative_to(self.workspace))
                except (ToolPolicyError, ValueError):
                    continue
                if (
                    relative in included
                    or not target.exists()
                    or self._is_runtime_path(target)
                ):
                    continue
                archive.add(
                    target,
                    arcname=relative,
                    recursive=target.is_dir(),
                    filter=lambda info: (
                        None
                        if Path(info.name).parts
                        and Path(info.name).parts[0] == ".lightcoder"
                        else info
                    ),
                )
                included.add(relative)
        if not included:
            snapshot.unlink(missing_ok=True)
            return ""
        return str(snapshot.relative_to(self.store.run_dir))

    def _is_runtime_path(self, path: Path) -> bool:
        try:
            relative = path.resolve().relative_to(self.workspace)
        except ValueError:
            return False
        return bool(relative.parts and relative.parts[0] == ".lightcoder")


class CommandSupervisor:
    def __init__(self, tools: WorkspaceTools) -> None:
        self.tools = tools

    def run(
        self,
        command: str,
        *,
        cwd: str = ".",
        timeout_seconds: float = 1_800,
        background: bool = False,
        env: dict[str, str] | None = None,
    ) -> ToolResult:
        started = time.monotonic()
        command_id = new_id("cmd")
        log_path = self.tools.store.command_log_path(command_id)
        try:
            if not command.strip():
                raise ToolPolicyError("command must not be empty")
            workdir = self.tools.resolve_path(cwd)
            if not workdir.is_dir():
                raise ToolPolicyError(f"cwd is not a directory: {cwd}")
            process_env = os.environ.copy()
            process_env.update(env or {})
            if background:
                return self._start_background(
                    command_id, command, workdir, log_path, process_env, started
                )
            process = subprocess.Popen(
                command,
                cwd=workdir,
                env=process_env,
                shell=True,
                executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                start_new_session=True,
            )
            try:
                output, _ = process.communicate(timeout=max(0.1, timeout_seconds))
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    output, _ = process.communicate(timeout=2.0)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    output, _ = process.communicate()
                output += f"\ncommand timed out after {timeout_seconds:.1f}s"
                exit_code = 124
            log_path.write_text(output, encoding="utf-8")
            return ToolResult(
                "bash",
                command_id,
                exit_code == 0,
                time.monotonic() - started,
                output=self.tools.compact(output),
                raw_log=str(log_path.relative_to(self.tools.store.run_dir)),
                exit_code=exit_code,
            )
        except (OSError, ToolPolicyError) as error:
            return ToolResult(
                "bash", command_id, False, time.monotonic() - started, output=str(error)
            )

    def _start_background(
        self,
        command_id: str,
        command: str,
        workdir: Path,
        log_path: Path,
        env: dict[str, str],
        started: float,
    ) -> ToolResult:
        log_handle = log_path.open("w", encoding="utf-8")
        try:
            process = subprocess.Popen(
                command,
                cwd=workdir,
                env=env,
                shell=True,
                executable="/bin/bash",
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
        finally:
            log_handle.close()
        metadata = {
            "id": command_id,
            "command": command,
            "cwd": str(workdir.relative_to(self.tools.workspace)),
            "pid": process.pid,
            "process_start_ticks": self._process_start_ticks(process.pid),
            "started_at": utc_now(),
            "status": "running",
            "log": str(log_path.relative_to(self.tools.store.run_dir)),
        }
        self._write_metadata(command_id, metadata)
        return ToolResult(
            "bash",
            command_id,
            True,
            time.monotonic() - started,
            output=f"background command started with pid {process.pid}",
            raw_log=metadata["log"],
            background_id=command_id,
            data={"pid": process.pid, "status": "running"},
        )

    def poll(self, command_id: str) -> ToolResult:
        started = time.monotonic()
        try:
            metadata = self._read_metadata(command_id)
            pid = int(metadata["pid"])
            exit_code = self._reap_exit_code(pid)
            running = exit_code is None and self._metadata_process_running(metadata)
            log_path = self.tools.store.run_dir / str(metadata["log"])
            output = (
                log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.exists()
                else ""
            )
            status = "running" if running else "exited"
            metadata["status"] = status
            if exit_code is not None:
                metadata["exit_code"] = exit_code
            metadata["polled_at"] = utc_now()
            self._write_metadata(command_id, metadata)
            return ToolResult(
                "poll",
                new_id("poll"),
                True,
                time.monotonic() - started,
                output=self.tools.compact(output),
                raw_log=str(metadata["log"]),
                background_id=command_id,
                exit_code=exit_code,
                data={"pid": pid, "status": status},
            )
        except (OSError, ValueError, KeyError) as error:
            return ToolResult(
                "poll",
                new_id("poll"),
                False,
                time.monotonic() - started,
                output=str(error),
            )

    def terminate(self, command_id: str, *, grace_seconds: float = 5.0) -> ToolResult:
        started = time.monotonic()
        try:
            metadata = self._read_metadata(command_id)
            pid = int(metadata["pid"])
            if self._metadata_process_running(metadata):
                os.killpg(pid, signal.SIGTERM)
                deadline = time.monotonic() + max(0.0, grace_seconds)
                while (
                    self._metadata_process_running(metadata)
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.05)
                if self._metadata_process_running(metadata):
                    os.killpg(pid, signal.SIGKILL)
            metadata["status"] = "terminated"
            metadata["terminated_at"] = utc_now()
            self._write_metadata(command_id, metadata)
            return ToolResult(
                "terminate",
                new_id("term"),
                True,
                time.monotonic() - started,
                output=f"terminated background command {command_id}",
                background_id=command_id,
            )
        except (OSError, ValueError, KeyError) as error:
            return ToolResult(
                "terminate",
                new_id("term"),
                False,
                time.monotonic() - started,
                output=str(error),
            )

    def recover(self) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        for path in sorted(self.tools.store.commands_dir.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if value.get(
                    "status"
                ) == "running" and not self._metadata_process_running(value):
                    value["status"] = "exited"
                    value["recovered_at"] = utc_now()
                    self._write_metadata(str(value["id"]), value)
                recovered.append(value)
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
        return recovered

    def _metadata_path(self, command_id: str) -> Path:
        if not command_id.startswith("cmd-") or "/" in command_id:
            raise ValueError("invalid command id")
        return self.tools.store.commands_dir / f"{command_id}.json"

    def _read_metadata(self, command_id: str) -> dict[str, Any]:
        return json.loads(self._metadata_path(command_id).read_text(encoding="utf-8"))

    def _write_metadata(self, command_id: str, value: dict[str, Any]) -> None:
        self.tools.store._atomic_json(self._metadata_path(command_id), value)

    @staticmethod
    def _pid_running(pid: int) -> bool:
        stat = Path(f"/proc/{pid}/stat")
        try:
            if stat.read_text(encoding="utf-8").split()[2] == "Z":
                return False
        except (OSError, IndexError):
            pass
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    @staticmethod
    def _process_start_ticks(pid: int) -> int | None:
        try:
            return int(
                Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[21]
            )
        except (OSError, IndexError, ValueError):
            return None

    def _metadata_process_running(self, metadata: dict[str, Any]) -> bool:
        pid = int(metadata["pid"])
        expected = metadata.get("process_start_ticks")
        if expected is not None and self._process_start_ticks(pid) != int(expected):
            return False
        return self._pid_running(pid)

    @staticmethod
    def _reap_exit_code(pid: int) -> int | None:
        try:
            waited, status = os.waitpid(pid, os.WNOHANG)
        except (ChildProcessError, OSError):
            return None
        if waited == 0:
            return None
        return os.waitstatus_to_exitcode(status)
