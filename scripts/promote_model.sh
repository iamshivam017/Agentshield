#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
MODEL_VERSION="${MODEL_VERSION:-}"
OPERATOR_ID="${OPERATOR_ID:-}"
OPERATOR_API_KEY="${OPERATOR_API_KEY:-}"

if [[ -z "$BASE_URL" || -z "$MODEL_VERSION" || -z "$OPERATOR_ID" || -z "$OPERATOR_API_KEY" ]]; then
  cat >&2 <<'USAGE'
Usage:
  BASE_URL=https://... \
  MODEL_VERSION=baseline-logistic-v1 \
  OPERATOR_ID=admin-operator \
  OPERATOR_API_KEY=... \
  ./scripts/promote_model.sh

The target API must already have the verified model artifact registered at TRAINED.
USAGE
  exit 2
fi

curl_args=(
  --fail
  --silent
  --show-error
  -X POST
  -H "X-Operator-API-Key: $OPERATOR_API_KEY"
  -H "X-Operator-ID: $OPERATOR_ID"
)

post_transition() {
  local transition="$1"
  echo "Promoting $MODEL_VERSION -> $transition"
  curl "${curl_args[@]}" "${BASE_URL%/}/api/v1/models/${MODEL_VERSION}/${transition}"
  printf '\n'
}

curl --fail --silent --show-error "${BASE_URL%/}/health/ready" >/dev/null
post_transition evaluate
post_transition candidate
post_transition approve
post_transition activate

echo "Model $MODEL_VERSION is approved and activated through the governed control plane."
