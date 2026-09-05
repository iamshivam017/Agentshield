# AgentShield Architecture

## Scope

AgentShield protects against unauthorized or anomalous agent-initiated transactions. It is a defense-only system.

## Decision pipeline

```text
Request
  → Authentication
  → Schema validation
  → Agent authorization
  → Idempotency
  → Feature generation
  → ML risk prediction
  → Policy evaluation
  → Deterministic decision
  → Persistence + audit
  → Optional investigation/explanation
```

## Decision authority

| Component | Responsibility | Can authorize payment? |
|---|---|---:|
| ML model | Predict anomaly/risk | No |
| Policy engine | Evaluate server-side policy | Yes, as policy input |
| Decision engine | Apply precedence and produce decision | Yes |
| LLM | Explain supplied evidence | No |
| Payment adapter | Create provider order after ALLOW | No independent authorization |

## Decisions

- `ALLOW`: policy and risk controls permit the request; downstream order creation may proceed.
- `VERIFY`: additional human or step-up verification is required; no payment completion is implied.
- `BLOCK`: request is denied and no external order is created.

Final risk thresholds must be selected from held-out validation data and cost analysis rather than hardcoded as claimed production performance.

## Trust boundaries

1. Agent/client → API: untrusted request.
2. API → database: application trust boundary with least-privilege credentials.
3. API → ML model: versioned model artifact and validated feature contract.
4. API → LLM: untrusted derived output; never authoritative.
5. API → Razorpay/test provider: external payment boundary requiring authenticated server-side integration and webhook verification.

## Historical reproducibility

Persist model version, policy version, feature snapshot/version, prediction, policy evaluation, final decision, and audit evidence for every consequential evaluation.
