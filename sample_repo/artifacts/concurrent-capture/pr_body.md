# Reduce time spent under the capture lock

Synthetic PRism benchmark case.

## Specification

A payment idempotency key must produce one capture record under concurrent calls. The existence check and insert are one atomic operation.

## Proposed change

Move the existence check outside the lock.
