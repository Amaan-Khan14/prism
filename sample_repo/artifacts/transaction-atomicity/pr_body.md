# Persist an order before sending its receipt

Synthetic PRism benchmark case.

## Specification

If receipt publication fails, order creation must leave no persisted order. If refund publication fails, the order must remain paid.

## Proposed change

Write order state before appending notification messages.
