# LightCoder Documentation

This directory contains the authoritative design for LightCoder. LightCoder is a
training-free, single-LLM coding agent for work that can outlive one model context
and continue for hours.

## Document Map

1. [System architecture](architecture/overview.md)
2. [State machine](architecture/state-machine.md)
3. [Persistent state schema](architecture/state-schema.md)
4. [Context and memory](architecture/context-memory.md)
5. [Tools and skills](architecture/tools-skills.md)
6. [SWE-Marathon evaluation](evaluation/swe-marathon.md)
7. [Experiment runbook](evaluation/runbook.md)
8. [Optional managed evaluation](evaluation/managed-evaluation.md)
9. [Implementation status](implementation-status.md)
10. [Usage](usage.md)

## Authority

The documents above describe the target and implemented architecture. Historical
research-pipeline documents are not retained because an LLM supervisor and
framework-managed worker hierarchy are outside LightCoder's design.

The following invariants apply across all documents:

- Exactly one LLM policy performs semantic task work.
- The run controller is deterministic code, not another agent.
- State, evidence, checkpoints, and best artifacts survive context rotation.
- Attempt, replan, and context-rotation counts do not terminate a run.
- Completion requires external evidence and deterministic guards.
- Runtime routing never checks benchmark or task names.
