# Synthetic shop

This is an authored PRism fixture, not a production shop. It has payments,
orders, notifications, and tenant-scoped access. Each corpus branch changes
one behavior against the contracts in the PR body.

Run the baseline suite with `PYTHONPATH=src python3 -m unittest discover -s tests`.
