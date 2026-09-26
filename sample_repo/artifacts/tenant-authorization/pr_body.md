# Simplify order lookup by ID

Synthetic PRism benchmark case.

## Specification

Order lookup must enforce the caller's tenant_id, even when the order ID is valid.

## Proposed change

Use order ID as the sole lookup key.
