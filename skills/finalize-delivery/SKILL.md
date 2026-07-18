---
name: finalize-delivery
description: Perform final repository-wide verification and produce an evidence-backed delivery summary or a deadline-bounded partial handoff. Use only after work items finish or deadline hardening begins.
---

# Finalize Delivery

Finalization is a separate integration phase. Do not infer global correctness from milestone checks.

## Verification

1. Inspect the complete diff, untracked files, generated artifacts, and repository instructions.
2. Remove accidental debug output, secrets, temporary artifacts, and bookkeeping from the deliverable.
3. Run the broadest credible clean build, test, lint, type, compatibility, or benchmark gates within remaining time.
4. Confirm commands exercised current sources rather than stale caches.
5. Check that all mandatory work items are accepted unless deadline hardening explicitly permits partial delivery.
6. Return `final_verified` with current-revision successful command evidence, a concise basis, and real residual risks.

## Delivery

After the controller accepts final verification, return `final_delivery` containing:

- what behavior or artifact was delivered;
- validation commands and outcomes;
- changed files at a useful level of grouping;
- unresolved risks, skipped checks, or environment limitations.

Do not claim a skipped check passed. Do not hide partial completion behind vague language. Under deadline hardening, preserve the best verified integrated state and clearly distinguish accepted from incomplete work.

## Exit

Only the controller can mark the run completed or limit-paused. Produce the requested action; do not invent a separate completion state.
