# Project Guide for AI Assistants

This document guides AI assistants on how to navigate and work with this project.

## Project Overview

**What this project does:** Read `README.rst` for project description and purpose.

**Project type:** Python package — a personal learning project for exploring Snowflake. Documentation, examples, and code in this repo are written to help an individual developer learn Snowflake hands-on (SQL, Cortex, Snowpark, CLI, pricing, etc.).

## Snowflake CLI

This project uses the official `snowflake-cli` (the `snow` command) for any Snowflake operation that can be done from the command line — account setup, running SQL, managing warehouses/databases/objects, deploying Streamlit apps, working with Snowpark, etc.

**Project standard — always invoke it via `uvx`, never install it globally:**

```bash
uvx --from snowflake-cli snow <subcommand> [args...]
```

Examples:

```bash
uvx --from snowflake-cli snow --version
uvx --from snowflake-cli snow connection list
uvx --from snowflake-cli snow sql -q "SELECT CURRENT_VERSION();"
```

Rationale: `uvx` runs the CLI in an ephemeral, isolated environment managed by `uv`, so we don't pollute the project's `.venv` or the system Python, and we always get a pinned, reproducible toolchain. When writing docs, examples, or automation in this repo, **always show the `uvx --from snowflake-cli snow ...` form** rather than a bare `snow ...` invocation.

## Core Configuration Files

### Tool & Dependency Management
- `mise.toml` - Task runner and tool version management (Python 3.12, uv, claude)
- `pyproject.toml` - Python dependencies and package metadata
- `.venv/` - Virtual environment directory (created by uv)

Use `mise ls python --current` to see the exact Python version in use.

### CI/CD & Testing
- `.github/workflows/main.yml` - GitHub Actions CI workflow
- `codecov.yml` + `.coveragerc` - Code coverage reporting (codecov.io)
- `.readthedocs.yml` - Documentation hosting (readthedocs.org)

### Documentation
- `docs/source/` - Sphinx documentation source files
- `docs/source/conf.py` - Sphinx configuration

## Development Workflow

### Task Management
List all available tasks:
```bash
mise tasks ls
```

Run a specific task:
```bash
mise run ${task_name}
```

**Key tasks:**
- `inst` - Install all dependencies using uv (fast package manager)
- `cov` - Run unit tests with coverage report
- `build-doc` - Build Sphinx documentation

For complete task reference, run `mise run list-tasks` to generate `.claude/mise-tasks.md`.

### Testing Philosophy
This project uses **pytest** with a special pattern that allows running individual test files as standalone scripts.

**Example:** See `tests/test_api.py` - the `if __name__ == "__main__":` block demonstrates this pattern. It runs pytest as a subprocess with coverage tracking for the specific module, enabling quick isolated testing during development.

## Working with This Project

**Approach:**
1. Don't load entire files unnecessarily - read specific files only when needed
2. Use task commands (`mise run`) instead of direct tool invocation
3. Follow the testing pattern when creating new test files
4. Reference configuration files for specific settings rather than assuming defaults

**Tools in use:**
- **mise-en-place** - Development tool management
- **uv** - Fast Python package management
- **pytest** - Unit testing framework
- **sphinx** - Documentation generation
