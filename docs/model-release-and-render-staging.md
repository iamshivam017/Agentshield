# Model Release and Render Staging Runbook

This runbook is the bridge from a green repository build to a reproducible staging deployment.

## 1. Preconditions

Use a successful CI run from `main` whose ML job uploaded:

`agentshield-risk-model-smoke-<commit_sha>`

The release workflow re-downloads that artifact and verifies it again before publication.

Current validated example:

- CI run: `34166263917` (run #284)
- commit: `8a22fbbfb71bde17bf7044057e71c90a4d235fbf`
- model artifact: `agentshield-risk-model-smoke-8a22fbbfb71bde17bf7044057e71c90a4d235fbf`
- model version: `baseline-logistic-v1`
- artifact digest: `sha256:59fe91c5c9a6ade614a3543d76479eaf3c47ff7aa841ac90191fae8390049b22`

Do not copy the model artifact into the repository. The release asset is the durable deployment source.

## 2. Publish an approved model release

Open GitHub Actions → `Release Risk Model` → `Run workflow` and supply:

- `ci_run_id`: successful CI run ID
- `commit_sha`: exact commit that produced the model artifact
- `model_version`: exact `model_version` from CI metadata
- `approval`: `APPROVE`
- `release_tag`: unique immutable tag such as `model-v1.0.0`

The workflow:

1. checks out the exact target commit;
2. requires the explicit approval token;
3. downloads the CI model artifact for that commit;
4. verifies the artifact checksum and metadata;
5. requires the source metadata status to be `EVALUATED`;
6. changes only the release metadata status to `APPROVED`;
7. re-verifies the approved artifact;
8. publishes `model.joblib`, `metadata.json`, `SHA256SUMS`, and `release-manifest.json` as GitHub Release assets.

The release must exist before staging is configured. A missing release means there is no durable model URL to configure.

## 3. Render API environment contract

For the `agentshield-api` Render service, use:

| Variable | Required value |
| --- | --- |
| `APP_ENV` | `staging` |
| `REQUIRE_AGENT_AUTH` | `true` |
| `REQUIRE_OPERATOR_AUTH` | `true` |
| `JWT_SECRET` | generated secret |
| `AGENT_API_KEY` | operator-provided secret |
| `OPERATOR_ADMIN_API_KEY` | operator-provided secret |
| `OPERATOR_ANALYST_API_KEY` | operator-provided secret |
| `OPERATOR_VIEWER_API_KEY` | operator-provided secret |
| `RISK_MODEL_ARTIFACT_URL` | GitHub Release asset URL for `model.joblib` |
| `RISK_MODEL_METADATA_URL` | GitHub Release asset URL for `metadata.json` |
| `RISK_MODEL_ARTIFACT_SHA256` | exact SHA-256 from `SHA256SUMS` / metadata |
| `RISK_MODEL_VERSION` | exact release metadata `model_version` |
| `RISK_MODEL_ARTIFACT_PATH` | `/tmp/agentshield-model/model.joblib` |
| `RISK_MODEL_METADATA_PATH` | `/tmp/agentshield-model/metadata.json` |
| `RAZORPAY_KEY_ID` | Razorpay Test Mode key ID |
| `RAZORPAY_KEY_SECRET` | Razorpay Test Mode secret |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay Test Mode webhook secret |
| `LLM_PROVIDER` | `none` for deterministic staging unless an approved read-only provider is configured |

Never commit these secret values to Git. Keep provider credentials and operator credentials in Render environment configuration.

## 4. API startup behavior

The API bootstrap helper downloads the configured artifact and metadata before serving staging/production traffic. It then verifies:

- configured SHA-256 equals the downloaded artifact SHA-256;
- metadata contains the required governance fields;
- metadata SHA-256 equals the downloaded artifact SHA-256;
- metadata version equals `RISK_MODEL_VERSION`;
- feature version is supported (`v1`);
- metadata status is `APPROVED` or `ACTIVE`.

A missing or incomplete staging model configuration must fail closed.

After bootstrap, the API container automatically registers the verified artifact in the model registry as `TRAINED` (idempotently, with checksum enforcement). It does not bypass the governed promotion lifecycle.

## 5. Render web service

The `agentshield-web` service receives the internal API target from the Render Blueprint. The application-side proxy normalizes the target to a usable HTTP URL before forwarding requests.

Do not expose the API directly from browser-side code when the server-side proxy is the configured path.

## 6. First staging verification

After deployment, verify in this order:

1. API liveness: `/health/live`
2. API readiness: `/health/ready`
3. API model-serving path using a non-mutating risk evaluation
4. authenticated control-plane access
5. web application root page
6. authenticated Policies / Models / Audit / System Health views
7. a deterministic risk scenario for ALLOW / VERIFY / BLOCK
8. Razorpay Test Mode order creation only from an `ALLOW` decision
9. webhook replay and stale-event protection
10. reconciliation / recovery behavior

For repeatable target validation, use GitHub Actions → `Staging Validation` with the deployed API URL. The workflow checks liveness/readiness, then runs the selected k6 profile and uploads the result JSON as evidence. Set repository/environment secrets `AGENT_ID`, `MERCHANT_ID`, and `AGENT_API_KEY` before running it.

Record the exact deployment URL, model release tag, model SHA-256, and test transaction IDs in release evidence.

## 7. Performance gate

Repository k6 script validation is not target performance evidence. Run smoke first, then load/stress/soak against the actual staging API target and retain the result artifacts.

The repository defines these profiles:

- `smoke`
- `load`
- `stress`
- `soak`

Do not mark the performance gate complete from syntax validation alone.

## 8. Current evidence boundary

Repository state currently proves:

- CI run #284 is green;
- the CI model artifact is generated and checksum-verified;
- the API image now idempotently registers the verified model artifact at startup;
- the release workflow is committed and ready;
- the Render Blueprint is committed and wired for staging variables.

Repository state does **not** by itself prove:

- a published model release exists;
- Render services have actually been deployed;
- live Razorpay Test Mode execution has succeeded;
- target load/stress/soak measurements exist;
- centralized production metrics have been deployed.

Only promote those final gates after the corresponding external evidence is captured.
