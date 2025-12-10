# fpr

**Find Project Root** — heuristically detect the root of a project directory.

## Installation

```bash
pip install modularizer-fpr
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

# Custom weights (repeatable)
fpr -w "./Cargo.toml:100" -w "target:-50"

# Weights as JSON string
fpr --weights-json '{"./Cargo.toml": 100, "target": -50}'

# Weights from JSON file
fpr --weights-file my-weights.json

# Skip default weights entirely
fpr --no-defaults -w "./package.json:100"

# Combine sources (priority: defaults < file < json < -w)
fpr --weights-file base.json -w "./my-marker:200"
```

### Python API

```python
from fpr import find_project_root, score_all, score_directory, WEIGHTS

# Find the project root (returns a Path)
root = find_project_root()
root = find_project_root("/some/nested/path")
root = find_project_root(verbose=True)  # prints all scores

# Get scores for all candidate directories
best_path, best_score, all_scores = score_all("/some/nested/path")
# best_path: Path to highest-scoring directory
# best_score: int score of that directory  
# all_scores: dict mapping Path -> score for all candidates

# Score a single directory
score = score_directory("/my/project")

# Use custom weights
custom_weights = {
    "./Cargo.toml": 100,  # strongly prefer Rust projects
    "target": -50,        # penalize being inside target/
}
root = find_project_root(weights=custom_weights)
```

## How It Works

`fpr` walks up from the starting directory, scoring each ancestor based on common project markers.

### Pattern Types

Weights use glob-like patterns with `*` (any except `/`) and `**` (any including `/`):

| Pattern | Matches |
|---------|---------|
| `./foo` | Directory contains a child named `foo` |
| `foo` | Directory itself is named `foo` |
| `**/foo/**/` | `foo` appears anywhere in ancestry |
| `**/foo/` | Direct parent is `foo` |
| `**/foo/*/` | Grandparent is `foo` |

### Default Weights

Positive weights (project indicators):
- **Config files**: `./pyproject.toml`, `./package.json`, `./Cargo.toml`, `./go.mod`, etc.
- **VCS directories**: `./.git`, `./.hg`, `./.svn`
- **Lock files**: `./poetry.lock`, `./yarn.lock`, `./package-lock.json`
- **Dev tooling**: `./Dockerfile`, `./Makefile`, `./.editorconfig`

Negative weights (penalties):
- **Name patterns**: `src`, `dist`, `node_modules`, `venv`, etc.
- **Parent patterns**: `**/venv/**/`, `**/node_modules/**/`, etc.

Returns the highest-scoring directory, or the starting directory if no strong signals are found.

## License

Unlicense

