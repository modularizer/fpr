# fpr

**Find Project Root** — heuristically detect the root of a project directory.

## Installation

```bash
pip install .
```

## Usage

### Command Line

```bash
# From current directory
fpr

# From a specific path
fpr /path/to/some/nested/folder

# Show scoring for all candidate directories
fpr --verbose

# Output relative path
fpr --rel
```

### Python API

```python
from fpr import find_project_root

root = find_project_root()  # starts from cwd
root = find_project_root("/some/nested/path")
```

## How It Works

`fpr` walks up from the starting directory, scoring each ancestor based on common project markers:

- **Config files**: `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, etc.
- **VCS directories**: `.git`, `.hg`, `.svn`
- **Lock files**: `poetry.lock`, `yarn.lock`, `package-lock.json`
- **Dev tooling**: `Dockerfile`, `Makefile`, `.editorconfig`

Directories like `src/`, `node_modules/`, or `venv/` are penalized to avoid false positives.

Returns the highest-scoring directory, or the starting directory if no strong signals are found.

## License

Unlicense

