# Tools And Skills

## Minimal Tool Surface

LightCoder exposes three primary workspace tools:

- `bash`: execute a command with cwd, timeout, output capture, and optional background mode;
- `read`: read a bounded UTF-8 file range inside the workspace;
- `write`: atomically replace a file inside the workspace.

Search, listing, patching, compilation, and tests are performed through `bash`.
`read`, `write`, and command cwd paths are resolved beneath the configured
workspace. Runtime metadata paths and harness-protected paths are denied for direct
writes. Arbitrary shell commands require an OS/container sandbox; string filtering
is intentionally not presented as a security boundary.

## Tool Result Contract

Every result includes tool name, call id, success flag, duration, compact output,
raw-log reference when needed, and any affected paths. Large output is truncated in
context but preserved on disk.

## Skill Roles

Dispatchable skills are intentionally small in number:

### Core workflow

- profile-task
- plan-work
- execute-work-item
- verify-work-item
- diagnose-and-replan
- manage-context-handoff
- finalize-delivery

### Domain playbooks

- repair
- feature
- project
- transformation
- optimization
- generalist

### Execution overlay

- long-horizon

Core skills define semantic work. Domain playbooks supply task-specific heuristics,
while `long-horizon` supplies multi-hour operating discipline. State
selection, completion checks, checkpointing, and routing are controller code rather
than skills.

## Loading

The registry reads only skill metadata during discovery. A request loads one core
skill and, when useful, one playbook. Loading dozens of node instructions into the
same context is prohibited.

## Anti-Contamination

Skills cannot contain benchmark names, task identifiers, hidden verifier details,
gold solutions, or one-run facts. Benchmark adapters may provide deadline and
protected-path configuration, but cannot alter semantic completion rules.
