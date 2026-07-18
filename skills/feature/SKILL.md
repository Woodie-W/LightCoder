---
name: feature
description: Add a feature within an existing system by deriving its contract, integrating a vertical slice, and validating compatibility and edge behavior. Load when new behavior under an established architecture dominates.
---

# Feature Playbook

Derive the feature contract from the request, adjacent APIs, repository conventions, tests, and compatibility guarantees. Resolve ambiguity by inspecting existing behavior before inventing a new convention.

Implement a narrow end-to-end slice early: public entry point, core behavior, persistence or transport boundary if relevant, and one executable acceptance path. Then expand edge cases and ergonomics.

Preserve:

- backward-compatible defaults unless the task requires a break;
- error and cancellation semantics;
- serialization and versioning expectations;
- security and resource boundaries;
- documentation or generated API surfaces required by the repository.

Test contract behavior, not implementation structure. Include representative success, invalid input, boundary values, and interaction with an existing feature. Avoid adding abstraction that only serves a hypothetical future variant.
