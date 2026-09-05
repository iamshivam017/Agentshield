# AgentShield Rate Limiting

AgentShield uses a fixed-window request limiter at the API boundary.

In development and test environments, the limiter can use bounded in-process state. In staging and production, a Redis-backed store is required so multiple API replicas share the same counters. If Redis is unavailable in a protected environment, the API fails closed with `503 rate_limit_backend_unavailable` instead of silently reverting to per-process limits.

The Redis implementation uses an atomic Lua script: `INCR` increments the current time bucket and `EXPIRE` is set only on the first increment. The rate-limit key contains the configured window, time bucket, and caller key. This prevents one API instance from bypassing a shared limit simply by routing through another replica.

The current request middleware keys the limit by client host. For a deployment behind a trusted proxy, the ingress/load-balancer layer should provide a validated client identity before replacing this key with an end-user or agent identity. Untrusted forwarded headers must not be used directly.

Recommended production configuration:

```text
REDIS_URL=redis://:<password>@redis.internal:6379/0
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
```

Redis availability and latency should be monitored because the rate limiter sits on the API request path. A Redis outage in staging/production is treated as an availability/security dependency failure rather than bypassed.
