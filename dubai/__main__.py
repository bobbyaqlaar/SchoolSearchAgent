"""Allow `uv run python -m dubai` as the sync CLI entrypoint."""

from dubai.cli import main

raise SystemExit(main())
