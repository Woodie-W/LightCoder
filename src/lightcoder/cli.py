from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .controller import RunController
from .evaluation import (
    adopt_evaluator,
    evaluation_store,
    find_attempt,
    format_attempt,
    format_log,
    load_attempts,
    restore_attempt,
    submit_evaluation,
)
from .model import OpenAICompatibleClient
from .reporting import build_run_report
from .store import StateStore, default_state_root, discover_runs


def parse_duration(value: str) -> float:
    text = value.strip().lower()
    factors = {"s": 1.0, "m": 60.0, "h": 3_600.0, "d": 86_400.0}
    suffix = text[-1:] if text[-1:] in factors else "s"
    number = text[:-1] if text.endswith(tuple(factors)) else text
    try:
        seconds = float(number) * factors[suffix]
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid duration: {value}") from error
    if seconds < 0:
        raise argparse.ArgumentTypeError("duration must be non-negative")
    return seconds


def default_skills_root() -> Path:
    configured = os.getenv("LIGHTCODER_SKILLS")
    if configured:
        return Path(configured).expanduser().resolve()
    source_tree = Path(__file__).resolve().parents[2] / "skills"
    if (source_tree / "manifest.json").is_file():
        return source_tree
    try:
        for entry in importlib.metadata.files("lightcoder") or []:
            normalized = str(entry).replace("\\", "/")
            if normalized.endswith("share/lightcoder/skills/manifest.json"):
                return Path(entry.locate()).resolve().parent
    except importlib.metadata.PackageNotFoundError:
        pass
    return source_tree


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lightcoder", description="Persistent long-running coding agent"
    )
    parser.add_argument("--version", action="version", version="LightCoder 0.2.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="create and execute a run")
    run.add_argument("objective")
    run.add_argument("--workspace", type=Path, default=Path.cwd())
    run.add_argument("--state-root", type=Path)
    run.add_argument(
        "--wall-time", type=parse_duration, default=0.0, metavar="DURATION"
    )
    run.add_argument(
        "--managed-eval",
        action="store_true",
        help="advertise the optional command-based evaluation loop to the agent",
    )
    _add_runtime_options(run, ablations=True)

    resume = subparsers.add_parser("resume", help="resume a persistent run")
    resume.add_argument("run_id")
    resume.add_argument("--note", default="")
    _add_existing_run_options(resume)

    step = subparsers.add_parser("step", help="execute one controller cycle")
    step.add_argument("run_id")
    _add_existing_run_options(step, cycles=False)

    status = subparsers.add_parser("status", help="print canonical run state")
    status.add_argument("run_id")
    _add_state_location_options(status)

    report = subparsers.add_parser("report", help="print machine-readable run metrics")
    report.add_argument("run_id")
    _add_state_location_options(report)

    cancel = subparsers.add_parser(
        "cancel", help="cancel a run and its background commands"
    )
    cancel.add_argument("run_id")
    cancel.add_argument("--reason", default="cancelled by operator")
    _add_existing_run_options(cancel, cycles=False)

    listing = subparsers.add_parser("list", help="list persistent runs")
    _add_state_location_options(listing)

    eval_parser = subparsers.add_parser(
        "eval",
        help="commit and evaluate the current solution and evaluator",
        description="""Commit the current workspace and run the editable managed evaluator.

Create .lightcoder-eval/evaluate.py. It runs with the submitted workspace as
its working directory and must print a JSON object on its final non-empty line:
  {"metrics": {"partial": 0.5}, "test_points": []}

Create .lightcoder-eval/metrics.toml:
  primary = "partial"
  timeout_seconds = 600
  [metrics.partial]
  direction = "maximize"

Changing either file automatically creates a new evaluator version. Scores are
only compared when evaluator version, primary metric, and direction all match.

To adopt a script that already prints `S3=0.5` (or `S3: 0.5`) and immediately
record a baseline:
  lightcoder eval --adopt evaluate.py --primary S3 -- graph1 graph2 result.align
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    eval_parser.add_argument("-m", "--message", default="")
    eval_parser.add_argument("--adopt", type=Path, metavar="SCRIPT")
    eval_parser.add_argument("--primary")
    eval_parser.add_argument(
        "--direction", choices=["maximize", "minimize"], default="maximize"
    )
    eval_parser.add_argument("--eval-timeout", type=float, default=600)
    _add_evaluation_location_options(eval_parser)
    eval_parser.add_argument("evaluator_args", nargs=argparse.REMAINDER)

    eval_log = subparsers.add_parser("log", help="list managed evaluation attempts")
    _add_evaluation_location_options(eval_log)
    eval_log.add_argument("--json", action="store_true")

    show = subparsers.add_parser("show", help="show one managed evaluation attempt")
    show.add_argument("attempt_id")
    _add_evaluation_location_options(show)

    checkout = subparsers.add_parser(
        "checkout", help="restore the clean workspace snapshot from an attempt"
    )
    checkout.add_argument("attempt_id")
    _add_evaluation_location_options(checkout)
    return parser


def _add_state_location_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--state-root", type=Path)


def _add_evaluation_location_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(os.getenv("LIGHTCODER_EVAL_WORKSPACE", Path.cwd())),
    )
    parser.add_argument("--store", type=Path)


def _add_runtime_options(
    parser: argparse.ArgumentParser, *, cycles: bool = True, ablations: bool = False
) -> None:
    parser.add_argument("--skills", type=Path, default=default_skills_root())
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--api-key")
    parser.add_argument("--context-window", type=int, default=128_000)
    parser.add_argument("--protected-path", type=Path, action="append", default=[])
    parser.add_argument(
        "--watch", action="store_true", help="stream controller events to stderr"
    )
    if ablations:
        parser.add_argument(
            "--ablation",
            action="append",
            default=[],
            choices=["standard-only", "no-handoffs", "no-checkpoints"],
            help="persist an experimental mechanism ablation; may be repeated",
        )
    if cycles:
        parser.add_argument(
            "--max-cycles",
            type=int,
            help="yield after this many cycles without terminating the persistent run",
        )


def _add_existing_run_options(
    parser: argparse.ArgumentParser, *, cycles: bool = True
) -> None:
    _add_state_location_options(parser)
    _add_runtime_options(parser, cycles=cycles)


def _state_root(args: argparse.Namespace) -> Path:
    return (
        (args.state_root or default_state_root(args.workspace)).expanduser().resolve()
    )


def _model(args: argparse.Namespace) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url=args.base_url, model=args.model, api_key=args.api_key
    )


def _controller(args: argparse.Namespace) -> RunController:
    store = StateStore(_state_root(args), args.run_id)
    if args.watch:
        store.event_sink = _print_event
    return RunController(
        store,
        _model(args),
        skills_root=args.skills,
        protected_paths=args.protected_path,
        context_window_tokens=args.context_window,
    )


def _print_state(state: object) -> None:
    value = state.to_dict()  # type: ignore[attr-defined]
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _print_event(event: dict[str, object]) -> None:
    print(
        json.dumps(event, ensure_ascii=False, sort_keys=True),
        file=sys.stderr,
        flush=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            controller = RunController.create(
                args.objective,
                args.workspace,
                _model(args),
                state_root=args.state_root,
                skills_root=args.skills,
                wall_time_seconds=args.wall_time,
                protected_paths=args.protected_path,
                context_window_tokens=args.context_window,
                ablations=args.ablation,
                managed_evaluation=args.managed_eval,
            )
            if args.watch:
                controller.store.event_sink = _print_event
            print(f"run_id={controller.store.run_id}", file=sys.stderr, flush=True)
            state = controller.run(max_cycles=args.max_cycles)
        elif args.command == "resume":
            controller = _controller(args)
            current = controller.store.load()
            if current.status == "waiting":
                controller.resume(args.note)
            elif args.note:
                controller.store.append_transcript(
                    "user", args.note, kind="external_input"
                )
            state = controller.run(max_cycles=args.max_cycles)
        elif args.command == "step":
            state = _controller(args).step()
        elif args.command == "status":
            state = StateStore(_state_root(args), args.run_id).load()
        elif args.command == "report":
            print(
                json.dumps(
                    build_run_report(StateStore(_state_root(args), args.run_id)),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        elif args.command == "cancel":
            state = _controller(args).cancel(args.reason)
        elif args.command == "list":
            print(json.dumps(discover_runs(_state_root(args)), indent=2))
            return 0
        elif args.command == "eval":
            evaluator_args = list(args.evaluator_args)
            if evaluator_args[:1] == ["--"]:
                evaluator_args = evaluator_args[1:]
            if args.adopt:
                if not args.primary:
                    raise ValueError("--adopt requires --primary")
                adopt_evaluator(
                    args.workspace,
                    args.adopt,
                    primary=args.primary,
                    direction=args.direction,
                    arguments=evaluator_args,
                    timeout_seconds=args.eval_timeout,
                )
            elif evaluator_args:
                raise ValueError("evaluator arguments require --adopt")
            record = submit_evaluation(
                args.workspace, store=args.store, message=args.message
            )
            print(format_attempt(record))
            return 0 if record.get("status") == "completed" else 1
        elif args.command == "log":
            attempts = load_attempts(evaluation_store(args.workspace, args.store))
            print(
                json.dumps(attempts, ensure_ascii=False, indent=2)
                if args.json
                else format_log(attempts)
            )
            return 0
        elif args.command == "show":
            attempt = find_attempt(
                evaluation_store(args.workspace, args.store), args.attempt_id
            )
            print(json.dumps(attempt, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        elif args.command == "checkout":
            attempt = restore_attempt(
                args.workspace, args.attempt_id, store=args.store
            )
            print(
                f"restored {attempt['id']} from commit {attempt['commit']}; "
                "HEAD was not moved"
            )
            return 0
        else:
            parser.error(f"unknown command: {args.command}")
        _print_state(state)
        return 0
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"lightcoder: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
