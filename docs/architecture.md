# Architecture

```text
synthetic CSV
  -> machine-readable contract
  -> Python validation
  -> SQLite normalized warehouse
  -> SQL marts
  -> relational QA
  -> independent Python profile
  -> Python/SQL parity
  -> readiness + temporal gates
  -> deterministic reports/dashboard
  -> tests + CI + Docker
```

The private scientific repository is not an upstream runtime dependency of this public companion.
