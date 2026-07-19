from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import tarfile
import tempfile
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

    def edit(
        self,
        path: str,
        old: str,
        new: str,
        *,
        replace_all: bool = False,
    ) -> ToolResult:
        started = time.monotonic()
        call_id = new_id("edit")
        try:
            target = self.resolve_path(path, write=True)
            if not target.is_file():
                raise FileNotFoundError(path)
            if not old:
                raise ToolPolicyError("edit old text must not be empty")
            content = target.read_text(encoding="utf-8", errors="strict")
            matches = content.count(old)
            if matches == 0:
                raise ToolPolicyError("edit old text was not found")
            if matches > 1 and not replace_all:
                raise ToolPolicyError(
                    f"edit old text matched {matches} times; use replace_all explicitly"
                )
            updated = content.replace(old, new) if replace_all else content.replace(old, new, 1)
            temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            relative = str(target.relative_to(self.workspace))
            return ToolResult(
                "edit",
                call_id,
                True,
                time.monotonic() - started,
                output=f"replaced {matches if replace_all else 1} occurrence(s) in {relative}",
                affected_paths=[relative],
            )
        except (OSError, UnicodeError, ToolPolicyError) as error:
            return ToolResult(
                "edit", call_id, False, time.monotonic() - started, output=str(error)
            )

    def compact(self, value: str) -> str:
        if len(value) <= self.max_context_chars:
            return value
        half = self.max_context_chars // 2
        omitted = len(value) - (half * 2)
        return f"{value[:half]}\n... {omitted} characters omitted; see raw log ...\n{value[-half:]}"

    def workspace_revision(self) -> str:
        hasher = hashlib.sha256()
        try:
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
        except FileNotFoundError:
            git = None
        if git is not None and git.returncode == 0:
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.workspace,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            ).stdout.strip()
            hasher.update(head.encode())
            diff = subprocess.run(
                [
                    "git",
                    "diff",
                    "--binary",
                    "HEAD",
                    "--",
                    ".",
                    ":(exclude).git",
                    ":(exclude).lightcoder",
                    ":(exclude).venv",
                    ":(exclude)node_modules",
                    ":(exclude)target",
                    ":(exclude)venv",
                ],
                cwd=self.workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            hasher.update(diff.stdout)
            for entry in git.stdout.split(b"\0"):
                if len(entry) <= 3:
                    continue
                path = entry[3:].decode(errors="surrogateescape")
                target = self.workspace / path
                if self._is_runtime_path(target):
                    continue
                hasher.update(entry)
                if entry.startswith(b"?? ") and target.is_file():
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
        try:
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
        except FileNotFoundError:
            result = None
        if result is None or result.returncode != 0:
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
            path = text[3:]
            if self._is_runtime_path(self.workspace / path):
                continue
            paths.append(path)
            if text[0] in {"R", "C"} or text[1] in {"R", "C"}:
                skip_rename_source = True
        return sorted(set(paths))

    def git_head(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.workspace,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError:
            return ""
        return result.stdout.strip() if result.returncode == 0 else ""

    def create_checkpoint_snapshot(self, checkpoint_id: str, paths: list[str]) -> str:
        snapshot = self.store.checkpoints_dir / f"{checkpoint_id}.tar.gz"
        temporary = snapshot.with_name(snapshot.name + ".tmp")
        included: set[str] = set()
        try:
            with tarfile.open(temporary, "w:gz") as archive:
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
            if included:
                os.replace(temporary, snapshot)
        finally:
            temporary.unlink(missing_ok=True)
        if not included:
            return ""
        return str(snapshot.relative_to(self.store.run_dir))

    def restore_checkpoint_snapshot(self, snapshot_path: str) -> list[str]:
        """Restore regular files from a controller-created checkpoint archive."""
        if not snapshot_path:
            return []
        snapshot = (self.store.run_dir / snapshot_path).resolve()
        try:
            snapshot.relative_to(self.store.checkpoints_dir.resolve())
        except ValueError as error:
            raise ToolPolicyError("checkpoint snapshot is outside the run store") from error
        if not snapshot.is_file():
            raise FileNotFoundError(f"checkpoint snapshot not found: {snapshot_path}")

        restored: list[str] = []
        staging = Path(
            tempfile.mkdtemp(
                prefix=".lightcoder-checkpoint-restore-", dir=self.workspace
            )
        )
        try:
            staged_files: list[tuple[Path, Path, int, str]] = []
            with tarfile.open(snapshot, "r:gz") as archive:
                for member in archive.getmembers():
                    relative = Path(member.name)
                    if relative.is_absolute() or ".." in relative.parts:
                        raise ToolPolicyError("unsafe path in checkpoint snapshot")
                    target = (self.workspace / relative).resolve()
                    try:
                        target.relative_to(self.workspace)
                    except ValueError as error:
                        raise ToolPolicyError(
                            "checkpoint member escapes workspace"
                        ) from error
                    if member.isdir():
                        continue
                    if not member.isfile():
                        continue
                    source = archive.extractfile(member)
                    if source is None:
                        continue
                    staged = staging / relative
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    with source, staged.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
                    os.chmod(staged, member.mode & 0o777)
                    staged_files.append(
                        (staged, target, member.mode & 0o777, str(relative))
                    )
            # Validate and stage the complete archive before replacing any live
            # artifact. Each final file replacement is atomic on the workspace
            # filesystem, so a reader never observes a partially written file.
            for staged, target, mode, relative in staged_files:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, target)
                os.chmod(target, mode)
                restored.append(relative)
            return restored
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _is_runtime_path(self, path: Path) -> bool:
        try:
            relative = path.resolve().relative_to(self.workspace)
        except ValueError:
            return False
        if not relative.parts:
            return False
        ignored_parts = {
            ".git",
            ".lightcoder",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "node_modules",
            "target",
            "venv",
        }
        return any(part in ignored_parts for part in relative.parts)


class CommandSupervisor:
    """Small job broker used by the LLM-facing run/start/poll/logs/stop tools."""

    DEFAULT_RUN_TIMEOUT_SECONDS = 300.0
    MAX_RUN_TIMEOUT_SECONDS = 1_200.0

    def __init__(self, tools: WorkspaceTools) -> None:
        self.tools = tools

    def run(
        self,
        command: str,
        *,
        cwd: str = ".",
        timeout_seconds: float | None = None,
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
            # Kept only for backwards-compatible callers.  The LLM contract
            # exposes this explicitly as `start`, rather than a boolean on a
            # general shell tool.
            if background:
                return self.start(
                    command, cwd=cwd, env=env
                )
            bounded_timeout = min(
                self.MAX_RUN_TIMEOUT_SECONDS,
                max(
                    0.1,
                    (
                        timeout_seconds
                        if timeout_seconds is not None
                        else self.DEFAULT_RUN_TIMEOUT_SECONDS
                    ),
                ),
            )
            with log_path.open("w", encoding="utf-8") as log_handle:
                process = subprocess.Popen(
                    command,
                    cwd=workdir,
                    env=process_env,
                    shell=True,
                    executable="/bin/bash",
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
                try:
                    # Wait for the shell process only.  Its output is written
                    # directly to a durable file, so an accidental `cmd &`
                    # child cannot retain a pipe and block the controller.
                    process.wait(timeout=bounded_timeout)
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    self._terminate_process_group(process.pid)
                    process.wait(timeout=2.0)
                    exit_code = 124
        except subprocess.TimeoutExpired:
            # A stubborn process group is already signalled above; still
            # produce a recoverable tool result instead of trapping the agent.
            exit_code = 124
            bounded_timeout = timeout_seconds or self.DEFAULT_RUN_TIMEOUT_SECONDS
        except (OSError, ToolPolicyError) as error:
            return ToolResult(
                "run", command_id, False, time.monotonic() - started, output=str(error)
            )

        output = log_path.read_text(encoding="utf-8", errors="replace")
        if exit_code == 124:
            output += f"\ncommand timed out after {bounded_timeout:.1f}s"
        elif self._process_group_running(process.pid):
            # A foreground action that spawns `server &` is neither observable
            # nor controllable by later poll/stop actions.  Kill it and make
            # the recovery path explicit to the model.
            self._terminate_process_group(process.pid)
            exit_code = 125
            output += (
                "\nforeground command left background descendants; they were "
                "terminated. Use the start action for services or long jobs."
            )
        log_path.write_text(output, encoding="utf-8")
        return ToolResult(
            "run",
            command_id,
            exit_code == 0,
            time.monotonic() - started,
            output=self.tools.compact(output),
            raw_log=str(log_path.relative_to(self.tools.store.run_dir)),
            exit_code=exit_code,
        )

    def start(
        self,
        command: str,
        *,
        cwd: str = ".",
        env: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> ToolResult:
        """Start a managed long-running job and immediately return its id."""
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
            return self._start_background(
                command_id,
                command,
                workdir,
                log_path,
                process_env,
                started,
                timeout_seconds=timeout_seconds,
            )
        except (OSError, ToolPolicyError) as error:
            return ToolResult(
                "start", command_id, False, time.monotonic() - started, output=str(error)
            )

    def _start_background(
        self,
        command_id: str,
        command: str,
        workdir: Path,
        log_path: Path,
        env: dict[str, str],
        started: float,
        *,
        timeout_seconds: float | None,
    ) -> ToolResult:
        bounded_timeout = (
            max(1.0, float(timeout_seconds))
            if timeout_seconds is not None
            else None
        )
        launched_command = command
        if bounded_timeout is not None:
            # The wrapper is deliberately inside the managed process group.  It
            # survives a controller crash and enforces the task's own remaining
            # wall-time, rather than inventing a short limit for valid searches.
            launched_command = (
                "timeout --signal=TERM --kill-after=15s "
                f"{bounded_timeout:.3f}s /bin/bash -lc {shlex.quote(command)}"
            )
        log_handle = log_path.open("w", encoding="utf-8")
        try:
            process = subprocess.Popen(
                launched_command,
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
            "timeout_seconds": bounded_timeout,
        }
        self._write_metadata(command_id, metadata)
        return ToolResult(
            "start",
            command_id,
            True,
            time.monotonic() - started,
            output=f"managed job started with pid {process.pid}",
            raw_log=metadata["log"],
            background_id=command_id,
            data={
                "pid": process.pid,
                "status": "running",
                "timeout_seconds": bounded_timeout,
            },
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

    def read_output(
        self, command_id: str, *, start_line: int = 1, max_lines: int = 400
    ) -> ToolResult:
        """Read any range of a command's durable raw log after context truncation."""
        started = time.monotonic()
        try:
            if not command_id.startswith("cmd-") or "/" in command_id:
                raise ValueError("invalid command id")
            log_path = self.tools.store.command_log_path(command_id)
            lines = log_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            first = max(0, start_line - 1)
            count = max(1, min(max_lines, 2_000))
            selected = lines[first : first + count]
            output = "\n".join(
                f"{index}: {line}"
                for index, line in enumerate(selected, first + 1)
            )
            if first + len(selected) < len(lines):
                output += f"\n... truncated; {len(lines)} total lines"
            return ToolResult(
                "read_command_output",
                new_id("log"),
                True,
                time.monotonic() - started,
                output=output,
                raw_log=str(log_path.relative_to(self.tools.store.run_dir)),
                background_id=command_id,
                data={
                    "command_id": command_id,
                    "start_line": start_line,
                    "max_lines": max_lines,
                },
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            return ToolResult(
                "read_command_output",
                new_id("log"),
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
                "stop",
                new_id("term"),
                True,
                time.monotonic() - started,
                output=f"terminated background command {command_id}",
                background_id=command_id,
            )
        except (OSError, ValueError, KeyError) as error:
            return ToolResult(
                "stop",
                new_id("term"),
                False,
                time.monotonic() - started,
                output=str(error),
            )

    @staticmethod
    def _process_group_running(process_group_id: int) -> bool:
        try:
            os.killpg(process_group_id, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    @staticmethod
    def _terminate_process_group(process_group_id: int) -> None:
        try:
            os.killpg(process_group_id, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + 0.2
        while (
            CommandSupervisor._process_group_running(process_group_id)
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)
        if CommandSupervisor._process_group_running(process_group_id):
            try:
                os.killpg(process_group_id, signal.SIGKILL)
            except ProcessLookupError:
                pass

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
