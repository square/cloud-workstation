# This is the default recipe when no arguments are provided
[private]
default:
  @just --list --unsorted

docs:
  #!/usr/bin/env zsh
  cd docs
  uv run mkdocs serve

tests:
  #!/usr/bin/env zsh
  uv run pytest --cov=workstation tests
