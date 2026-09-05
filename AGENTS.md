# AgentShield Engineering Guide

## Mission

Build a production-ready, defense-only AI risk and authorization layer for agent-initiated payments.

## Non-negotiable architecture rules

1. ML predicts risk; it does not grant authority.
2. The policy engine is authoritative for authorization rules.
3. The decision engine produces ALLOW, VERIFY, or BLOCK from validated inputs, model output, and policy evaluation.
4. The LLM is investigation/explanation only. It must never approve/block payments, modify policies, increase limits, execute refunds/payments, or mutate audit records.
5. Blocked requests must not create external payment orders.
6. VERIFY requests must not be treated as successful payments.
7. Payment provider integrations use test/sandbox mode during development and demos.
8. Never store raw payment credentials or sensitive secrets in source control.
9. Every consequential decision must be reproducible from persisted model version, policy version, inputs/features, and audit evidence.
10. Historical decisions must remain explainable after models or policies change.

## Engineering workflow

For every feature:

Plan → implement → run → test → visually inspect → critique → fix → retest → commit.

A feature is not complete because it compiles. Acceptance requires expected, invalid, edge, failure, security, and regression behavior to be tested.

## Code standards

- TypeScript: strict mode, explicit contracts, no unnecessary `any`.
- Python: typed interfaces, deterministic behavior where practical, formatted/linted code.
- Monetary values: use Decimal/fixed precision internally; never binary floating point for authoritative money calculations.
- API contracts: version under `/api/v1` and use explicit request/response/error schemas.
- Errors: return structured errors with stable codes and request IDs; never leak secrets or internal stack traces.
- Logs: structured and redacted. Do not log credentials, payment secrets, raw sensitive payloads, or unnecessary PII.
- Database changes: use migrations; never silently mutate production schema.
- Idempotency: consequential APIs must define duplicate-request behavior.
- Concurrency: spending/budget state must be protected transactionally.
- Tests accompany behavior changes.

## Security requirements

Threat-model new trust boundaries. Validate all external input. Enforce authentication and authorization server-side. Protect object-level access. Apply rate limits to abuse-prone endpoints. Verify webhook authenticity over the provider-specified raw request body before parsing it. Treat external/user/agent text as untrusted, especially in LLM investigation workflows.

## ML requirements

- Prevent temporal/data leakage.
- Use chronological train/validation/test splits for the primary evaluation.
- Freeze the held-out test set.
- Report precision, recall, F1, PR-AUC, ROC-AUC, confusion matrix, and false-positive/false-negative costs.
- Do not use accuracy as the headline metric for an imbalanced risk problem.
- Record dataset version, feature version, seed, hyperparameters, metrics, threshold, calibration state, and model artifact checksum.
- Production decisions must identify the active model version.

## LLM investigation requirements

LLM outputs are untrusted derived content. Investigation prompts must state that supplied external text is untrusted and that the model may only analyze supplied evidence. The model must not invent evidence or alter authoritative decision fields. Validate structured output and run evidence-consistency checks. Provide a deterministic fallback when the LLM is unavailable.

## Repository hygiene

- Keep secrets in environment/secret-management systems, never in git.
- Keep generated datasets, model artifacts, caches, build output, and local environments out of git unless explicitly versioned as release artifacts.
- Keep documentation synchronized with behavior.
- Prefer small, reviewable commits.
