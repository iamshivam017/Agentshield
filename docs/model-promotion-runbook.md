# AgentShield Model Promotion Runbook

This runbook turns a verified training artifact into a governed registry version. It does not bypass the lifecycle or declare a production model active without environment evidence.

## Preconditions

- A trained `model.joblib` and `metadata.json` have passed `scripts/verify_model_artifact.py`.
- The artifact is stored in the intended environment artifact store with its recorded SHA-256.
- `DATABASE_URL` points to the target AgentShield database.
- The API is healthy and its model-serving configuration points to the same artifact and checksum before activation.
- An operator with `admin` role is available.

## Register the artifact

From an API-capable Python environment:

```bash
PYTHONPATH=apps/api/src:apps/api python scripts/verify_model_artifact.py /path/to/artifact
PYTHONPATH=apps/api/src:apps/api python scripts/register_model_artifact.py /path/to/artifact
```

Registration is checksum-checked and idempotent for an existing version with the same checksum. A checksum mismatch for an existing version is rejected.

The new version is persisted as `TRAINED` together with evaluation metadata. It must still move through the governed lifecycle:

```text
TRAINED -> EVALUATED -> CANDIDATE -> APPROVED -> ACTIVE
```

## Promote through the control plane

Use an authenticated admin operator. The API endpoints are:

```text
POST /api/v1/models/{version}/evaluate
POST /api/v1/models/{version}/candidate
POST /api/v1/models/{version}/approve
POST /api/v1/models/{version}/activate
```

Run them in order. The `evaluate` transition records that the persisted training/evaluation evidence has passed the governance checkpoint; it does not retrain or mutate model metrics.

Send both `X-Operator-API-Key` and `X-Operator-ID` headers required by the configured control-plane authentication policy.

Activation retires the previous active model transactionally. The API serving artifact path and checksum must match the activated registry record before serving traffic.

## Rollback

Rollback is another governed promotion, not a database edit. Choose a previously retired version whose artifact remains available, restore the serving configuration to that exact checksum, and promote it through `APPROVED -> ACTIVE` using the authenticated admin route. Capture the incident/change record and validation evidence.

## Evidence to retain

Record the model version, artifact SHA-256, dataset/feature versions, evaluation metrics, selected threshold, target environment, operator identity, promotion timestamps, and post-activation health/performance evidence.

A CI smoke artifact demonstrates the registration and serving contract; it is not production promotion evidence.
