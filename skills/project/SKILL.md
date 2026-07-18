---
name: project
description: Build or complete a multi-component software project through executable vertical milestones, explicit interfaces, and continuous integration. Load when broad capability construction dominates.
---

# Project Playbook

Establish an executable skeleton and the primary integration command before filling every component. Organize milestones around user-visible flows rather than directories or layers.

For each milestone:

1. define inputs, outputs, ownership, and failure semantics at component boundaries;
2. implement the thinnest integrated path;
3. test the boundary in isolation and through the main flow;
4. update configuration, packaging, and documentation needed to run it;
5. checkpoint only an integrated, recoverable state.

Defer optional polish until core flows are executable. Do not allow parallel stubs to drift without an integration oracle. Prefer existing project conventions and dependencies unless evidence shows they cannot meet the contract.

Final validation should begin from a clean environment and follow the same setup a new maintainer or harness would use. Treat missing build, launch, or test instructions as a project defect.
