import json
import os
import shlex
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from harbor.agents.installed.base import BaseInstalledAgent, with_prompt_template
from harbor.agents.utils import get_api_key_var_names_from_model_name
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trial.paths import EnvironmentPaths


class LightCoderHarborAgent(BaseInstalledAgent):
    SUPPORTS_RESUME = False
    MANAGED_EVALUATION = True
    ABLATIONS: tuple[str, ...] = ()

    _REMOTE_SRC_DIR = PurePosixPath("/installed-agent/lightcoder")
    _REMOTE_RUNTIME_DIR = PurePosixPath("/installed-agent/python-runtime")
    _OUTPUT_FILENAME = "lightcoder.txt"
    _REPORT_FILENAME = "lightcoder-report.json"
    _STATE_DIRNAME = "lightcoder-state"
    _FINAL_STATE_FILENAME = "lightcoder-final-state.json"

    _WORKSPACE_BY_TASK = {
        "find-network-alignments": "/app",
        "rust-java-lsp": "/workspace/rust-java-lsp",
        "ruby-rust-port": "/app/rj-rust",
        "stripe-clone": "/app",
        "vliw-kernel-optimization": "/app",
        "zstd-decoder": "/app/src",
    }

    _AGENT_TIMEOUT_BY_TASK = {
        "find-network-alignments": 18000,
        "rust-java-lsp": 10800,
        "ruby-rust-port": 36000,
        "stripe-clone": 14400,
        "vliw-kernel-optimization": 28800,
        "zstd-decoder": 18000,
    }

    _BASE_URL_BY_PROVIDER = {
        "deepseek": "https://api.deepseek.com/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "openai": "https://api.openai.com/v1",
    }

    @staticmethod
    def name() -> str:
        return "lightcoder"

    def get_version_command(self) -> str | None:
        return None

    def parse_version(self, stdout: str) -> str:
        return stdout.strip()

    def version(self) -> str | None:
        version_file = Path("/data/benchmarks/LightCoder/.git/HEAD")
        if version_file.exists():
            return "local"
        return "local"

    async def install(self, environment: BaseEnvironment) -> None:
        remote_src = self._REMOTE_SRC_DIR.as_posix()
        await self.exec_as_root(
            environment,
            command=f"mkdir -p {shlex.quote(remote_src)} /installed-agent",
        )
        await environment.upload_dir("/data/benchmarks/LightCoder", remote_src)

        py_check = await environment.exec("command -v python3 >/dev/null 2>&1")
        if py_check.return_code != 0:
            remote_runtime = self._REMOTE_RUNTIME_DIR.as_posix()
            await self.exec_as_root(
                environment,
                command=f"mkdir -p {shlex.quote(remote_runtime)}",
            )
            await environment.upload_dir(
                "/data/benchmarks/LightCoder/python-runtime",
                remote_runtime,
            )

    def _task_name(self, environment: BaseEnvironment) -> str:
        return environment.environment_name

    def _workspace_for_task(self, task_name: str) -> str:
        return self._WORKSPACE_BY_TASK.get(task_name, "/app")

    def _wall_time_for_task(self, task_name: str) -> str:
        override = os.environ.get("LIGHTCODER_WALL_TIME_SECONDS", "").strip()
        if override:
            try:
                seconds = int(override)
            except ValueError as error:
                raise ValueError(
                    "LIGHTCODER_WALL_TIME_SECONDS must be an integer"
                ) from error
            if seconds < 300:
                raise ValueError(
                    "LIGHTCODER_WALL_TIME_SECONDS must be at least 300"
                )
        else:
            seconds = self._AGENT_TIMEOUT_BY_TASK.get(task_name, 14400)
        seconds = max(60, seconds - 120)
        return f"{seconds}s"

    def _model_and_base_url(self) -> tuple[str, str, str]:
        if not self.model_name or "/" not in self.model_name:
            raise ValueError(
                "LightCoderHarborAgent requires model_name in provider/model format"
            )
        provider, model = self.model_name.split("/", 1)
        base_url = self._BASE_URL_BY_PROVIDER.get(provider)
        if not base_url:
            raise ValueError(f"Unsupported provider for LightCoderHarborAgent: {provider}")
        api_key_names = get_api_key_var_names_from_model_name(self.model_name)
        api_key = ""
        for name in api_key_names:
            api_key = os.environ.get(name, "")
            if api_key:
                break
        if not api_key:
            raise ValueError(
                f"Missing API key for {self.model_name}; tried {api_key_names}"
            )
        return model, base_url, api_key

    def _runtime_python_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        no_proxy_entries = {
            "localhost",
            "127.0.0.1",
            "::1",
            "api.deepseek.com",
            ".deepseek.com",
        }
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            value = os.environ.get(key)
            if not value:
                continue
            parsed = urlparse(value)
            host = (parsed.hostname or "").strip().lower()
            if host in {"127.0.0.1", "localhost", "::1"}:
                continue
            env[key] = value

        for key in ("NO_PROXY", "no_proxy"):
            value = os.environ.get(key, "")
            if value:
                no_proxy_entries.update(
                    item.strip() for item in value.split(",") if item.strip()
                )
            env[key] = ",".join(sorted(no_proxy_entries))
        return env

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        task_name = self._task_name(environment)
        workspace = self._workspace_for_task(task_name)
        wall_time = self._wall_time_for_task(task_name)
        model, base_url, api_key = self._model_and_base_url()

        agent_dir = EnvironmentPaths.agent_dir.as_posix()
        state_root = (EnvironmentPaths.agent_dir / self._STATE_DIRNAME).as_posix()
        output_path = (EnvironmentPaths.agent_dir / self._OUTPUT_FILENAME).as_posix()
        report_path = (EnvironmentPaths.agent_dir / self._REPORT_FILENAME).as_posix()
        final_state_path = (
            EnvironmentPaths.agent_dir / self._FINAL_STATE_FILENAME
        ).as_posix()
        remote_src = self._REMOTE_SRC_DIR.as_posix()
        remote_runtime = self._REMOTE_RUNTIME_DIR.as_posix()

        escaped_instruction = shlex.quote(instruction)
        escaped_workspace = shlex.quote(workspace)
        escaped_state_root = shlex.quote(state_root)
        escaped_output_path = shlex.quote(output_path)
        escaped_report_path = shlex.quote(report_path)
        escaped_final_state_path = shlex.quote(final_state_path)
        escaped_remote_src = shlex.quote(remote_src)
        experiment_options: list[str] = []
        if self.MANAGED_EVALUATION:
            experiment_options.append("--managed-eval")
        for ablation in self.ABLATIONS:
            experiment_options.extend(("--ablation", ablation))
        escaped_experiment_options = " ".join(
            shlex.quote(value) for value in experiment_options
        )

        command = f"""
set -euo pipefail
mkdir -p {shlex.quote(agent_dir)} {escaped_state_root}
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
  unset PYTHONHOME
else
  export PYTHONHOME={shlex.quote(remote_runtime)}
  export PATH={shlex.quote(remote_runtime)}/bin:$PATH
  export LD_LIBRARY_PATH={shlex.quote(remote_runtime)}/lib${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}
  export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
  PYTHON_BIN={shlex.quote(remote_runtime)}/bin/python3
fi
export PYTHONPATH={escaped_remote_src}/src
export LIGHTCODER_PYTHON="$PYTHON_BIN"
export PATH={escaped_remote_src}/bin:$PATH
STATUS=0
"$PYTHON_BIN" -m lightcoder.cli run {escaped_instruction} \
  --workspace {escaped_workspace} \
  --state-root {escaped_state_root} \
  --wall-time {shlex.quote(wall_time)} \
  --skills {escaped_remote_src}/skills \
  --base-url {shlex.quote(base_url)} \
  --model {shlex.quote(model)} \
  --context-window 128000 \
  {escaped_experiment_options} \
  --watch \
  > {escaped_final_state_path} 2> >(stdbuf -oL tee {escaped_output_path} >&2) || STATUS=$?
RUN_ID="$(find {escaped_state_root}/runs -mindepth 1 -maxdepth 1 -type d | sort | tail -n1 | xargs -r basename || true)"
while [ -n "$RUN_ID" ]; do
  RUN_STATUS="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["status"])' {escaped_state_root}/runs/$RUN_ID/state.json)"
  [ "$RUN_STATUS" = "waiting" ] || break
  # Background jobs are synchronous progress, not a reason to spend another
  # model call every few seconds. Resume at a coarse interval while waiting.
  sleep 30
  "$PYTHON_BIN" -m lightcoder.cli resume "$RUN_ID" \
    --state-root {escaped_state_root} \
    --skills {escaped_remote_src}/skills \
    --base-url {shlex.quote(base_url)} \
    --model {shlex.quote(model)} \
    --context-window 128000 \
    --watch \
    > {escaped_final_state_path} 2> >(stdbuf -oL tee -a {escaped_output_path} >&2) || STATUS=$?
done
if [ -n "$RUN_ID" ]; then
  "$PYTHON_BIN" -m lightcoder.cli report "$RUN_ID" --state-root {escaped_state_root} > {escaped_report_path} || true
fi
exit "$STATUS"
""".strip()

        runtime_env = self._runtime_python_env()
        runtime_env["LIGHTCODER_API_KEY"] = api_key
        await self.exec_as_agent(
            environment,
            command=command,
            cwd=workspace,
            env=runtime_env,
        )

    def populate_context_post_run(self, context: AgentContext) -> None:
        report_path = self.logs_dir / self._REPORT_FILENAME
        if not report_path.exists():
            return
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            return
        context.metadata = {
            "run_id": report.get("run_id"),
            "status": report.get("status"),
            "elapsed_seconds": report.get("elapsed_seconds"),
            "model_calls": report.get("model_calls"),
            "successful_model_responses": report.get("successful_model_responses"),
            "token_usage": report.get("token_usage", {}),
            "context_episodes": report.get("context_episodes"),
            "context_rotations": report.get("context_rotations"),
            "commands": report.get("commands"),
            "commands_failed": report.get("commands_failed"),
            "commands_passed": report.get("commands_passed"),
            "attempts": report.get("attempts"),
            "managed_evaluation": report.get("managed_evaluation"),
            "phase": report.get("phase"),
        }


class LightCoderA0FullAgent(LightCoderHarborAgent):
    @staticmethod
    def name() -> str:
        return "lightcoder-a0-full"


class LightCoderA1WorkGraphAgent(LightCoderHarborAgent):
    ABLATIONS = ("standard-only",)

    @staticmethod
    def name() -> str:
        return "lightcoder-a1-work-graph"


class LightCoderA2NoHandoffsAgent(LightCoderHarborAgent):
    ABLATIONS = ("no-handoffs",)

    @staticmethod
    def name() -> str:
        return "lightcoder-a2-no-handoffs"


class LightCoderA3NoCheckpointsAgent(LightCoderHarborAgent):
    ABLATIONS = ("no-checkpoints",)

    @staticmethod
    def name() -> str:
        return "lightcoder-a3-no-checkpoints"


class LightCoderA4NoManagedEvalAgent(LightCoderHarborAgent):
    MANAGED_EVALUATION = False

    @staticmethod
    def name() -> str:
        return "lightcoder-a4-no-managed-eval"
