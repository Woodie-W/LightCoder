# Coding Agent Node Skills

This self-contained package specifies the 98 nodes in the LightCoder business state machine. The deterministic runtime owns dispatch, persistence, route validation, context switching, limits, and terminal status. A skill defines only the work performed inside one dispatched node.

Each node skill contains:

- `Input State`: state fields read by the node;
- `Procedure`: node-specific operations;
- `State Updates`: the only fields the node may propose changing;
- `Routes`: legal outgoing transitions;
- `Constraints`: node-specific integrity rules;
- `Runtime Contract`: links to shared result, evidence, persistence, routing, and convergence rules.

Shared details are progressively disclosed from `references/`:

- `node-runtime-contract.md`: lifecycle of every node attempt;
- `state-contract.md`: state ownership and invariants;
- one `*-flow.md` file for each specialized loop and finalization.

`manifest.json` is the machine-readable registry. It includes node name, skill path, flow, kind, execution mode, input fields, allowed state updates, routes, terminal flag, and virtual flag. `PHASE_2_TASK_LOOP` is a virtual diagram/reporting node and is never dispatched.

`coding_agent_state_machines_loop_cn.docx` is the original business-flow overview. The Markdown contracts and manifest are authoritative where they are more specific.

Rebuild and validate from the repository root:

```bash
python tools/build_coding_agent_skills.py --enrich --build-zip
```
