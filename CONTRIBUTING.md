# Contributing

Read AGENTS.md and the architecture before making changes. Keep changes focused and
include tests and documentation. Submit contributions under GPL-3.0-or-later; keep
third-party notices intact. Do not include proprietary robot assets or credentials.

Install `pip install -e ".[dev]"`, then run `pytest`, `ruff check .`, `mypy src`, and
`python -m build`. Hardware claims require the exact robot/app/firmware/OS versions
and an explicit test record. Simulator tests are not evidence of physical safety.
