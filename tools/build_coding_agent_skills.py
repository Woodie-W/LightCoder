#!/usr/bin/env python3
"""Enrich, validate, and package the LightCoder node skill collection."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE = ROOT / "skills"
DEFAULT_ZIP = ROOT / "coding-agent-skills.zip"

ORCHESTRATION_NODES = {
    "START",
    "PHASE_1_QUICK_RECON",
    "ROUTE_TASK",
    "REPAIR_GRAPH",
    "FEATURE_GRAPH",
    "PROJECT_GRAPH",
    "OPTIMIZE_GRAPH",
    "TRANSFORM_GRAPH",
    "GENERALIST_GRAPH",
    "PHASE_2_TASK_LOOP",
    "PHASE_3_FINALIZE",
    "END",
}

VIRTUAL_NODES = {"PHASE_2_TASK_LOOP"}

FLOW_RANGES = (
    ("repair", "INITIALIZE_REPAIR_STATE", "REPAIR_COMPLETE"),
    ("feature", "INITIALIZE_FEATURE_STATE", "FEATURE_COMPLETE"),
    ("project", "INITIALIZE_PROJECT_STATE", "MAP_FAILURE_TO_MILESTONE"),
    ("optimization", "INITIALIZE_OPTIMIZATION_STATE", "ROLLBACK_TO_BEST_RESULT"),
    ("transform", "INITIALIZE_TRANSFORM_STATE", "TRANSFORM_COMPLETE"),
    ("generalist", "INITIALIZE_GENERALIST_STATE", "GENERALIST_COMPLETE"),
    ("finalize", "RUN_CLEAN_ENVIRONMENT_VALIDATION", "SUBMIT_PATCH_OR_PROJECT"),
)

CONTROL_NODES = {
    "START",
    "END",
    "PHASE_2_TASK_LOOP",
    "PHASE_3_FINALIZE",
    "REPAIR_GRAPH",
    "FEATURE_GRAPH",
    "PROJECT_GRAPH",
    "OPTIMIZE_GRAPH",
    "TRANSFORM_GRAPH",
    "GENERALIST_GRAPH",
    "REPAIR_LOOP_START",
    "FEATURE_LOOP_START",
    "PROJECT_LOOP_START",
    "OPTIMIZATION_LOOP_START",
    "TRANSFORM_LOOP_START",
    "GENERALIST_LOOP_START",
}

DELIVERY_NODES = {"GENERATE_CONCISE_REPORT", "SUBMIT_PATCH_OR_PROJECT"}

VERIFICATION_NODES = {
    "VERIFY_REPAIR",
    "VERIFY_ACCEPTANCE_AND_REGRESSION",
    "VERIFY_MILESTONE_AND_INTEGRATION",
    "RUN_END_TO_END_ACCEPTANCE",
    "RUN_CORRECTNESS_AND_PERFORMANCE_TESTS",
    "FINAL_PERFORMANCE_VALIDATION",
    "CAPTURE_BEHAVIOR_BASELINE",
    "CAPTURE_BUILD_COMPATIBILITY_BASELINE",
    "VERIFY_BUILD_BEHAVIOR_COMPATIBILITY",
    "TRANSFORM_FINAL_VALIDATION",
    "VERIFY_SUBGOAL",
    "RUN_CLEAN_ENVIRONMENT_VALIDATION",
    "INSPECT_FINAL_DIFF_AND_ARTIFACTS",
    "RUN_INTEGRITY_CHECK",
}

STATE_NODES = {
    "UPDATE_REPAIR_STATE",
    "UPDATE_FAILURE_SIGNATURE",
    "REPAIR_COMPLETE",
    "UPDATE_FEATURE_STATE",
    "FEATURE_COMPLETE",
    "CHECKPOINT_PROJECT_STATE",
    "UPDATE_PROJECT_STATE",
    "PROJECT_COMPLETE",
    "ACCEPT_CANDIDATE",
    "UPDATE_EXPERIMENT_STATE",
    "OPTIMIZATION_COMPLETE",
    "ACCEPT_TRANSFORMATION_STEP",
    "UPDATE_TRANSFORM_STATE",
    "TRANSFORM_COMPLETE",
    "UPDATE_GENERALIST_STATE",
    "GENERALIST_COMPLETE",
}

ACTION_PREFIXES = ("IMPLEMENT_", "APPLY_", "FIX_", "EXECUTE_", "REMOVE_")
ACTION_NODES = {
    "REPRODUCE_OR_INSPECT",
    "LOCALIZE_RELEVANT_CODE",
    "STABILIZE_AND_RETEST",
    "ROLLBACK_AND_REJECT",
    "ROLLBACK_TO_BEST_RESULT",
    "ROLLBACK_AND_DIAGNOSE",
}

DETERMINISTIC_TOOL_NODES = {
    "ACCEPT_CANDIDATE",
    "ACCEPT_TRANSFORMATION_STEP",
    "CHECKPOINT_PROJECT_STATE",
    "ROLLBACK_AND_REJECT",
    "ROLLBACK_TO_BEST_RESULT",
    "SUBMIT_PATCH_OR_PROJECT",
}

MODEL_TOOL_NODES = {"PHASE_1_QUICK_RECON"}

ALLOWED_STATE_ROOTS = {
    "context",
    "control",
    "delivery",
    "evidence_index",
    "external_run_config",
    "feature",
    "final_review",
    "final_validation",
    "generalist",
    "integrity",
    "memory_index",
    "optimization",
    "project",
    "recon_brief",
    "repair",
    "run",
    "skills",
    "task",
    "task_profile",
    "transform",
    "usage",
    "workspace",
}

RUNTIME_START = "<!-- runtime-contract:start -->"
RUNTIME_END = "<!-- runtime-contract:end -->"

FIELD_ALIASES = {
    "accepted_revision": ("workspace.accepted_revision",),
    "active_flow": ("control.active_flow",),
    "delivery_status": ("delivery.status",),
    "delivery_summary": ("delivery.summary",),
    "final_artifacts": ("delivery.final_artifacts",),
    "final_report": ("delivery.final_report",),
    "last_checkpoint": ("control.last_checkpoint",),
    "lifecycle": ("run",),
    "lifecycle.completed_at": ("run.completed_at",),
    "lifecycle.status": ("run.status",),
    "phase2_return_reason": ("control.phase2_return_reason",),
    "phase2_status": ("control.phase2_status",),
    "phase3_status": ("control.phase3_status",),
    "repository_state": ("workspace",),
    "routing_history": ("control.route_history",),
    "routing_reason": ("control.routing_reason",),
    "run_id": ("run.run_id",),
    "skill_registry": ("skills.registry",),
    "subgraph_state": ("control.subgraph_state",),
    "subgraph_status": ("control.subgraph_status",),
    "submission_metadata": ("delivery.submission_metadata",),
    "thread_id": ("context.session_id",),
    "user_task": ("task.user_task",),
    "workspace_path": ("workspace.root",),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--enrich", action="store_true", help="Write metadata and shared-contract links.")
    parser.add_argument("--build-zip", action="store_true", help="Build the package zip after validation.")
    return parser.parse_args()


def load_manifest(package: Path) -> list[dict[str, object]]:
    value = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("manifest.json must contain a list")
    return value


def flow_map(manifest: list[dict[str, object]]) -> dict[str, str]:
    nodes = [str(item["node"]) for item in manifest]
    result = {node: "orchestration" for node in ORCHESTRATION_NODES}
    for flow, first, last in FLOW_RANGES:
        start = nodes.index(first)
        stop = nodes.index(last)
        for node in nodes[start : stop + 1]:
            result[node] = flow
    missing = set(nodes) - set(result)
    if missing:
        raise ValueError(f"nodes have no flow assignment: {sorted(missing)}")
    return result


def node_kind(node: str) -> str:
    if node in CONTROL_NODES:
        return "control"
    if node in DELIVERY_NODES:
        return "delivery"
    if node in VERIFICATION_NODES:
        return "verification"
    if node in STATE_NODES:
        return "state"
    if node in ACTION_NODES or node.startswith(ACTION_PREFIXES):
        return "action"
    return "decision"


def execution_mode(kind: str, node: str) -> str:
    if node in DETERMINISTIC_TOOL_NODES:
        return "deterministic_tool"
    if node in MODEL_TOOL_NODES:
        return "tool_agent"
    if kind in {"control", "state"}:
        return "deterministic"
    if kind == "verification":
        return "isolated_verifier"
    if kind == "action":
        return "tool_agent"
    return "model_assisted"


def contract_block(flow: str, kind: str, mode: str, *, virtual: bool = False) -> str:
    if virtual:
        return f"""{RUNTIME_START}
## Runtime Contract

- Node kind: `{kind}`
- Execution mode: `{mode}`
- Virtual node: `true`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md), [`Shared State Contract`](../references/state-contract.md), and [`{flow.title()} Flow Contract`](../references/{flow}-flow.md) for diagram/reporting semantics.
- Never dispatch this node, create an attempt, call a model/tool, produce a `NodeResult`, or write state. Its routes are aggregate documentation edges only.
{RUNTIME_END}
"""
    return f"""{RUNTIME_START}
## Runtime Contract

- Node kind: `{kind}`
- Execution mode: `{mode}`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`{flow.title()} Flow Contract`](../references/{flow}-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
{RUNTIME_END}
"""


def flow_guard(package: Path, flow: str, node: str) -> str:
    reference = (package / "references" / f"{flow}-flow.md").read_text(encoding="utf-8")
    row = next(
        (line for line in reference.splitlines() if line.startswith(f"| `{node}` |")),
        "",
    )
    if not row:
        raise ValueError(f"{node}: missing flow-contract row")
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    if len(cells) < 4:
        raise ValueError(f"{node}: malformed flow-contract row")
    return cells[-1]


def kind_guidance(kind: str) -> tuple[list[str], list[str], list[str]]:
    if kind == "control":
        return (
            [
                "Require a committed state revision and no unresolved active attempt.",
                "Do not call the model or workspace mutation tools; derive the outcome from structured state.",
            ],
            [
                "Persist the selected route, guard result, previous node, and new state revision as a transition event.",
                "No repository diff or narrative evidence is expected from a pure control node.",
            ],
            [
                "On stale or invalid state, reload once and fail closed instead of guessing a route.",
                "If no legal guard matches, leave the active node unchanged and return an invalid-state blocker.",
            ],
        )
    if kind == "decision":
        return (
            [
                "Resolve every cited evidence id and compare viable alternatives before selecting one outcome.",
                "Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.",
            ],
            [
                "Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.",
                "A decision without new workspace effects should not create command evidence or change accepted revision.",
            ],
            [
                "If evidence is insufficient, choose a legal evidence-gathering/replan route rather than fabricate certainty.",
                "If candidates remain tied, prefer the smaller reversible action and record the tie.",
            ],
        )
    if kind == "action":
        return (
            [
                "Require a single active work item, a known rollback point, and a matching workspace revision.",
                "Inspect affected files immediately before editing and keep the change within the declared task scope.",
            ],
            [
                "Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.",
                "Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.",
            ],
            [
                "Preserve partial logs and the exact failure signature; do not silently broaden the patch after a deterministic failure.",
                "Restore the rollback point before abandoning a candidate when the node contract requires a clean accepted state.",
            ],
        )
    if kind == "verification":
        return (
            [
                "Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.",
                "Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.",
            ],
            [
                "Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.",
                "Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.",
            ],
            [
                "A timeout, missing dependency, flaky measurement, or unavailable service is inconclusive until classified.",
                "Never repair the candidate inside a verifier attempt; route the evidence back to an action or diagnosis node.",
            ],
        )
    if kind == "state":
        return (
            [
                "Require validated source evidence and compare-and-swap against the input state revision.",
                "Apply only declared state fields and preserve immutable attempt, failure, and evidence history.",
            ],
            [
                "Record the old/new state revisions, applied patch, source evidence ids, affected work items, and invariant checks.",
                "Change accepted revision only when the referenced verification passed at exactly that revision.",
            ],
            [
                "On revision conflict, discard the proposed patch, reload, and recompute; never merge stale state heuristically.",
                "Reject dangling evidence, artifact, work-item, or revision references without partially committing state.",
            ],
        )
    if kind == "delivery":
        return (
            [
                "Require a final validated revision, resolved mandatory outcomes, and no integrity blocker.",
                "Use only evidence-backed claims and the artifact inventory supplied by finalization.",
            ],
            [
                "Record delivered paths, content hashes, validated revision, evidence links, limitations, and idempotency key.",
                "The report must distinguish completed, partially completed, blocked, skipped, and out-of-scope work.",
            ],
            [
                "If an artifact or evidence reference is stale, return to finalization instead of editing the claim around it.",
                "On repeated submission, verify the existing idempotency record and do not duplicate delivery side effects.",
            ],
        )
    raise ValueError(f"unknown node kind: {kind}")


def format_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def canonical_fields(values: list[str], *, state_updates: bool = False) -> list[str]:
    result: list[str] = []
    for value in values:
        if value == "repository_state" and state_updates:
            replacements = ("workspace.current_revision", "workspace.dirty_files")
        else:
            replacements = FIELD_ALIASES.get(value, (value,))
        for replacement in replacements:
            if replacement not in result:
                result.append(replacement)
    return result


def bullet_body(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def detailed_skill_text(
    package: Path,
    text: str,
    *,
    node: str,
    flow: str,
    kind: str,
    virtual: bool = False,
) -> str:
    input_body = section(text, "Input State")
    procedure_body = section(text, "Procedure")
    updates_body = section(text, "State Updates")
    routes_body = section(text, "Routes")
    constraints_body = section(text, "Constraints")
    inputs = canonical_fields(bullet_items(input_body))
    updates = [] if virtual else canonical_fields(bullet_items(updates_body), state_updates=True)
    input_body = bullet_body(inputs)
    updates_body = bullet_body(updates) if updates else "None. This virtual node never writes state."
    routes = route_names(text)
    entry, evidence, failures = kind_guidance(kind)
    guard = flow_guard(package, flow, node)
    prefix = text.split("## Input State", 1)[0].rstrip()
    if virtual:
        return "\n".join(
            [
                prefix,
                "",
                "## Input State",
                "",
                input_body,
                "",
                "## Entry Criteria",
                "",
                f"- `{node}` is documentation-only and must not receive an attempt id.",
                "- Reporting and visualization code may read the declared inputs to aggregate concrete subgraph status.",
                "- Runtime dispatch to this node is always a controller/manifest error.",
                "",
                "## Procedure",
                "",
                procedure_body,
                "",
                "## Evidence And Artifacts",
                "",
                "- Do not create attempts, evidence, state patches, context, or repository artifacts for this node.",
                "- Derive aggregate status only from committed concrete-subgraph state and events.",
                "",
                "## Failure Handling",
                "",
                "- Reject runtime dispatch without changing state.",
                "- Recover by selecting the concrete graph already named by `control.active_flow`.",
                "",
                "## Exit Checklist",
                "",
                "- No `NodeResult`, state patch, evidence, or runtime route is emitted.",
                f"- Aggregate route meaning: {guard}.",
                f"- Diagram edges are {format_list(routes)} and are never runtime proposals from this node.",
                "",
                "## State Updates",
                "",
                updates_body,
                "",
                "## Routes",
                "",
                routes_body,
                "",
                "## Constraints",
                "",
                constraints_body,
                "",
            ]
        )
    if kind in {"action", "verification", "delivery"}:
        artifact_rule = "- Reference large command output, diffs, benchmarks, and generated artifacts by workspace-relative path and content hash."
    else:
        artifact_rule = "- Keep the result compact; reference existing evidence ids instead of copying logs or transcript text into state."
    if kind in {"control", "state"}:
        runtime_failure = "- A persistence, schema, or lease failure interrupts the attempt; it is not product evidence and must not consume a business retry."
    else:
        runtime_failure = "- Transport-level model/tool failures may use the runtime retry allowance; a repeatable product or command failure must leave the node with evidence."

    lines = [
        prefix,
        "",
        "## Input State",
        "",
        input_body,
        "",
        "## Entry Criteria",
        "",
        (
            f"- `{node}` is documentation-only and must not receive an attempt id."
            if virtual
            else f"- The controller must dispatch `{node}` in the `{flow}` flow with a unique attempt id."
        ),
        f"- Resolve the declared inputs before work begins: {format_list(inputs)}.",
        *[f"- {item}" for item in entry],
        "- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.",
        "",
        "## Procedure",
        "",
        procedure_body,
        "",
        "## Evidence And Artifacts",
        "",
        *[f"- {item}" for item in evidence],
        f"- Proposed state updates are limited to: {format_list(updates)}.",
        artifact_rule,
        "",
        "## Failure Handling",
        "",
        *[f"- {item}" for item in failures],
        runtime_failure,
        "- Preserve the current accepted revision and external limits on every failure path.",
        "",
        "## Exit Checklist",
        "",
        "- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.",
        "- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.",
        (
            "- No `state_patch`, evidence, or proposed runtime route is emitted."
            if virtual
            else "- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve."
        ),
        f"- Route guard applied: {guard}",
        (
            f"- Aggregate diagram edges are: {format_list(routes)}; they are not runtime route proposals."
            if virtual
            else (
                f"- The proposed route is one of: {format_list(routes)}."
                if routes
                else "- This node is terminal and must not propose a route."
            )
        ),
        "- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.",
        "",
        "## State Updates",
        "",
        updates_body,
        "",
        "## Routes",
        "",
        routes_body,
        "",
        "## Constraints",
        "",
        constraints_body,
        "",
    ]
    return "\n".join(lines)


def enrich(package: Path, manifest: list[dict[str, object]]) -> None:
    flows = flow_map(manifest)
    for item in manifest:
        node = str(item["node"])
        kind = node_kind(node)
        mode = execution_mode(kind, node)
        item["flow"] = flows[node]
        item["kind"] = kind
        item["execution_mode"] = mode
        item["virtual"] = node in VIRTUAL_NODES
        item.pop("cn", None)

        path = package / str(item["path"])
        text = normalize_agent_facing_english(path.read_text(encoding="utf-8"), node)
        virtual = node in VIRTUAL_NODES
        block = contract_block(flows[node], kind, mode, virtual=virtual)
        if RUNTIME_START in text:
            pattern = re.compile(
                re.escape(RUNTIME_START) + r".*?" + re.escape(RUNTIME_END) + r"\n?",
                re.DOTALL,
            )
            text = pattern.sub(block, text, count=1)
        else:
            heading = re.search(r"^# .+$", text, flags=re.MULTILINE)
            if not heading:
                raise ValueError(f"{path}: missing H1")
            insert_at = heading.end()
            text = text[:insert_at] + "\n\n" + block + text[insert_at:].lstrip("\n")
        trigger = (
            f"Documentation-only virtual grouping for {node}; the controller must never dispatch it."
            if virtual
            else f"Use only when the LightCoder controller dispatches {node}."
        )
        description = frontmatter_value(text, "description")
        old_trigger = f"Use only when the LightCoder controller dispatches {node}."
        if virtual and old_trigger in description:
            description = description.replace(old_trigger, "").strip()
            text = re.sub(
                r"(?m)^description:\s*.+$",
                f"description: {description}",
                text,
                count=1,
            )
        if trigger not in frontmatter_value(text, "description"):
            text = re.sub(
                r"(?m)^description:\s*.+$",
                f"description: {frontmatter_value(text, 'description').rstrip()} {trigger}",
                text,
                count=1,
            )
        text = detailed_skill_text(
            package,
            text,
            node=node,
            flow=flows[node],
            kind=kind,
            virtual=virtual,
        )
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
        item["contract_version"] = 1
        item["input_state"] = bullet_items(section(text, "Input State"))
        item["state_updates"] = bullet_items(section(text, "State Updates"))
        item["routes"] = route_names(text)
        item["terminal"] = node == "END"

    (package / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def frontmatter_value(text: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", text)
    return match.group(1).strip() if match else ""


def normalize_agent_facing_english(text: str, node: str) -> str:
    description = frontmatter_value(text, "description")
    if "。" in description:
        description = description.split("。", 1)[1].lstrip()
    text = re.sub(
        r"(?m)^description:\s*.+$",
        f"description: {description}",
        text,
        count=1,
    )
    return re.sub(
        rf"(?m)^# {re.escape(node)}（[^\n]*）$",
        f"# {node}",
        text,
        count=1,
    )


def section(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^## {re.escape(name)}\s*$\n(.*?)(?=^## |\Z)",
        text,
    )
    return match.group(1).strip() if match else ""


def route_names(text: str) -> list[str]:
    routes = section(text, "Routes")
    return re.findall(r"`([A-Z][A-Z0-9_]+)`", routes)


def bullet_items(value: str) -> list[str]:
    items: list[str] = []
    for line in value.splitlines():
        match = re.match(r"\s*-\s+(.+?)\s*$", line)
        if match:
            items.append(match.group(1).strip().strip("`"))
    return items


def validate(package: Path, manifest: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    nodes = {str(item.get("node", "")) for item in manifest}
    skills = {str(item.get("skill", "")) for item in manifest}
    if len(nodes) != len(manifest):
        errors.append("manifest contains duplicate node names")
    if len(skills) != len(manifest):
        errors.append("manifest contains duplicate skill names")

    required_sections = {
        "Entry Criteria",
        "Evidence And Artifacts",
        "Failure Handling",
        "Exit Checklist",
        "Runtime Contract",
        "Input State",
        "Procedure",
        "State Updates",
        "Routes",
        "Constraints",
    }
    flows = flow_map(manifest)
    referenced_nodes: set[str] = set()
    adjacency: dict[str, set[str]] = {}

    for item in manifest:
        node = str(item.get("node", ""))
        skill = str(item.get("skill", ""))
        relpath = str(item.get("path", ""))
        path = package / relpath
        if not path.is_file():
            errors.append(f"{node}: missing {relpath}")
            continue
        text = path.read_text(encoding="utf-8")
        try:
            text.encode("ascii")
        except UnicodeEncodeError:
            errors.append(f"{node}: Agent-facing SKILL.md must contain ASCII English only")
        if len(text.splitlines()) > 500:
            errors.append(f"{node}: SKILL.md exceeds 500 lines")
        if frontmatter_value(text, "name") != skill:
            errors.append(f"{node}: frontmatter name does not match {skill}")
        description = frontmatter_value(text, "description")
        if len(description) < 30:
            errors.append(f"{node}: description is too vague")
        for name in sorted(required_sections):
            if not section(text, name):
                errors.append(f"{node}: missing or empty section {name}")
        flow = flows[node]
        for reference in (
            "../references/node-runtime-contract.md",
            "../references/state-contract.md",
            f"../references/{flow}-flow.md",
        ):
            if reference not in text:
                errors.append(f"{node}: missing reference {reference}")
        routes = route_names(text)
        adjacency[node] = set(routes)
        referenced_nodes.update(routes)
        for route in routes:
            if route not in nodes:
                errors.append(f"{node}: unknown route {route}")
        if node != "END" and not routes:
            errors.append(f"{node}: no machine-readable route")
        if node == "END" and "Terminal node" not in section(text, "Routes"):
            errors.append("END: terminal route declaration is missing")

        expected_kind = node_kind(node)
        expected_mode = execution_mode(expected_kind, node)
        procedure = section(text, "Procedure")
        procedure_steps = len(re.findall(r"(?m)^\d+\. ", procedure))
        minimum_steps = 3 if expected_kind in {"control", "state"} else 4
        if procedure_steps < minimum_steps:
            errors.append(
                f"{node}: {expected_kind} procedure needs at least {minimum_steps} numbered steps"
            )
        for field_name in [
            *bullet_items(section(text, "Input State")),
            *bullet_items(section(text, "State Updates")),
        ]:
            root = field_name.split(".", 1)[0]
            if root not in ALLOWED_STATE_ROOTS:
                errors.append(f"{node}: unknown state namespace {root!r} in {field_name!r}")
        for key, expected in (
            ("flow", flow),
            ("kind", expected_kind),
            ("execution_mode", expected_mode),
            ("virtual", node in VIRTUAL_NODES),
            ("contract_version", 1),
            ("input_state", bullet_items(section(text, "Input State"))),
            ("state_updates", bullet_items(section(text, "State Updates"))),
            ("routes", routes),
            ("terminal", node == "END"),
        ):
            if item.get(key) != expected:
                errors.append(f"{node}: manifest {key} must be {expected!r}")

        flow_reference = package / "references" / f"{flow}-flow.md"
        if flow_reference.is_file():
            reference_text = flow_reference.read_text(encoding="utf-8")
            rows = [line for line in reference_text.splitlines() if line.startswith(f"| `{node}` |")]
            if not rows:
                errors.append(f"{node}: not documented in {flow}-flow.md")
            elif node not in VIRTUAL_NODES:
                row = rows[0]
                for route in routes:
                    if f"`{route}`" not in row:
                        errors.append(f"{node}: route {route} has no guard in {flow}-flow.md")

    unreachable = nodes - referenced_nodes - {"START"} - VIRTUAL_NODES
    if unreachable:
        errors.append(f"nodes without any incoming route: {sorted(unreachable)}")

    reachable_from_start = graph_reachable(adjacency, "START")
    start_unreachable = nodes - reachable_from_start - VIRTUAL_NODES
    if start_unreachable:
        errors.append(f"nodes unreachable from START: {sorted(start_unreachable)}")
    reverse: dict[str, set[str]] = {node: set() for node in nodes}
    for source, targets in adjacency.items():
        for target in targets:
            reverse.setdefault(target, set()).add(source)
    can_reach_end = graph_reachable(reverse, "END")
    dead_end_nodes = nodes - can_reach_end - VIRTUAL_NODES
    if dead_end_nodes:
        errors.append(f"nodes that cannot reach END: {sorted(dead_end_nodes)}")

    for ref in (
        "node-runtime-contract.md",
        "state-contract.md",
        "orchestration-flow.md",
        "repair-flow.md",
        "feature-flow.md",
        "project-flow.md",
        "optimization-flow.md",
        "transform-flow.md",
        "generalist-flow.md",
        "finalize-flow.md",
    ):
        reference_path = package / "references" / ref
        if not reference_path.is_file():
            errors.append(f"missing shared reference: {ref}")
        else:
            try:
                reference_path.read_text(encoding="utf-8").encode("ascii")
            except UnicodeEncodeError:
                errors.append(f"Agent-facing reference must contain ASCII English only: {ref}")
    for relative in ("README.md", "manifest.json"):
        try:
            (package / relative).read_text(encoding="utf-8").encode("ascii")
        except UnicodeEncodeError:
            errors.append(f"Agent-facing package file must contain ASCII English only: {relative}")
    return errors


def graph_reachable(adjacency: dict[str, set[str]], start: str) -> set[str]:
    seen: set[str] = set()
    pending = [start]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(adjacency.get(node, ()))
    return seen


def build_zip(package: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts:
                continue
            archive.write(path, path.relative_to(package).as_posix())


def main() -> int:
    args = parse_args()
    package = args.package.resolve()
    manifest = load_manifest(package)
    if args.enrich:
        enrich(package, manifest)
        manifest = load_manifest(package)
    errors = validate(package, manifest)
    if errors:
        print("Skill package validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    if args.build_zip:
        build_zip(package, args.output.resolve())
    print(
        json.dumps(
            {
                "status": "ok",
                "nodes": len(manifest),
                "package": str(package),
                "zip": str(args.output.resolve()) if args.build_zip else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
