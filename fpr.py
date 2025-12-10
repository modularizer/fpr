"""Heuristically detect the root of a project directory"""
import argparse
import os
import re
from pathlib import Path


# Unified weights for project root detection
# Pattern types:
#   ./foo        - child pattern: matches if directory contains child named "foo"
#   foo          - name pattern: matches if directory itself is named "foo"
#   **/foo/**/   - parent pattern: matches if "foo" appears anywhere in ancestry
#   **/foo/      - parent pattern: matches if direct parent is "foo"
#   **/foo/*/    - parent pattern: matches if grandparent is "foo"
WEIGHTS = {
    # === Child patterns (./prefix) ===
    # Very strong signals (config files)
    "./pyproject.toml": 40,      # Python
    "./package.json": 40,        # Node / JS
    "./Cargo.toml": 40,          # Rust
    "./go.mod": 40,              # Go
    "./composer.json": 30,       # PHP
    "./Gemfile": 30,             # Ruby
    "./mix.exs": 30,             # Elixir

    # Version control
    "./.git": 30,
    "./.hg": 10,
    "./.svn": 10,

    # Python-specific but common
    "./requirements.txt": 25,
    "./Pipfile": 25,
    "./poetry.lock": 25,
    "./setup.py": 25,

    # Mono-repo / tool configs
    "./pnpm-lock.yaml": 15,
    "./yarn.lock": 15,
    "./package-lock.json": 15,
    "./tsconfig.json": 10,
    "./webpack.config.js": 10,
    "./next.config.js": 10,
    "./vite.config.js": 10,
    "./vite.config.ts": 10,
    "./angular.json": 10,

    # Infra / dev tooling
    "./docker-compose.yml": 15,
    "./Dockerfile": 10,
    "./Makefile": 10,
    "./.editorconfig": 5,

    # General project-ish files
    "./.env": 10,
    "./.env.local": 8,
    "./.env.example": 8,
    "./.gitignore": 5,
    "./README": 5,
    "./README.md": 5,
    "./README.rst": 5,
    "./LICENSE": 5,

    # Framework entrypoints (weak hints on their own)
    "./manage.py": 5,   # Django

    # Typical code / build dirs as children
    "./src": 10,
    "./dist": 10,
    "./build": 10,
    "./lib": 5,
    "./app": 5,
    "./server": 5,
    "./client": 5,
    "./backend": 5,
    "./frontend": 5,
    "./packages": 5,

    # Weak hints
    "./.vscode": 2,
    "./.idea": 2,

    # === Name patterns (no slashes) ===
    # Penalties for directories that are *probably not* the project root
    "src": -100,
    "dist": -100,
    "bin": -100,
    "lib": -100,
    "site-packages": -100,
    "assets": -100,
    "build": -100,
    "venv": -100,
    ".venv": -100,
    "env": -80,
    ".env": -80,
    "node_modules": -100,
    "__pycache__": -100,
    "": -100,

    # === Parent patterns (end with /) ===
    # Penalties if these appear anywhere in ancestry
    "**/.venv/**/": -200,
    "**/venv/**/": -200,
    "**/node_modules/**/": -200,
    "**/*env/**/": -100,         # matches 'env', '.env', 'myenv', etc.
    "**/__pycache__/**/": -150,
    "**/*cache*/**/": -50,       # generic cache-ish dirs
    "**/bin/**/": -100,
}



def _compile_pattern(pattern: str) -> re.Pattern[str]:
    r"""
    Convert a wildcard pattern into a compiled regex.
    Supports:
      **           => .* (matches anything including /)
      *            => [^/]* (matches anything except /)
      file.name    => ^file\.name$
    Examples:
      myfile*      => ^myfile[^/]*$
      *.json       => ^[^/]*\.json$
      **/*.json    => ^.*/[^/]*\.json$
    """
    escaped = re.escape(pattern)
    regex_str = "^" + escaped.replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$"
    return re.compile(regex_str)


def _categorize_patterns(weights: dict[str, int]) -> tuple[
    list[tuple[re.Pattern[str], int]],  # child patterns (./prefix)
    list[tuple[re.Pattern[str], int]],  # name patterns (no slashes)
    list[tuple[re.Pattern[str], int]],  # parent patterns (end with /)
]:
    """Categorize patterns by type and compile them."""
    child_patterns = []
    name_patterns = []
    parent_patterns = []

    for pattern, weight in weights.items():
        if pattern.startswith("./"):
            # Child pattern - compile without the ./ prefix for matching
            child_patterns.append((_compile_pattern(pattern), weight))
        elif pattern.endswith("/"):
            # Parent pattern - matches against parent path
            parent_patterns.append((_compile_pattern(pattern), weight))
        else:
            # Name pattern - matches directory name
            name_patterns.append((_compile_pattern(pattern), weight))

    return child_patterns, name_patterns, parent_patterns


def _apply_matches(text: str, patterns: list[tuple[re.Pattern[str], int]]) -> int:
    """Return sum of weights for any regex matching given text."""
    total = 0
    for regex, weight in patterns:
        if regex.match(text):
            total += weight
    return total


def score_directory(path: str | Path | None = None, weights: dict[str, int] | None = None) -> int:
    """
    Assign a heuristic score based on:
      - directory name (name patterns)
      - immediate children files/dirs (child patterns)
      - parent folder ancestry (parent patterns)
    """
    path = Path(path).expanduser().resolve() if path is not None else Path.cwd()
    if weights is None:
        weights = WEIGHTS
    child_regexes, name_regexes, parent_regexes = _categorize_patterns(weights)
    score = 0

    # Match name patterns against directory name
    score += _apply_matches(path.name, name_regexes)

    # Match parent patterns against parent path string
    # Build path like: /home/user/project/ for matching **/project/
    parent_path = str(path) + "/"
    score += _apply_matches(parent_path, parent_regexes)

    # Match child patterns against ./childname
    try:
        for child in path.iterdir():
            child_path = "./" + child.name
            score += _apply_matches(child_path, child_regexes)
    except Exception:
        pass

    return score


def score_all(start: str | Path | None = None, weights: dict[str, int] | None = None, rel: bool = False):
    """Score all candidate directories from start up to root."""
    start = Path(start).expanduser().resolve() if start is not None else Path.cwd()
    if weights is None:
        weights = WEIGHTS
    candidates = [start] + list(start.parents)

    scored = [(os.path.relpath(path, Path.cwd()) if rel else path, score_directory(path, weights)) for path in candidates]
    best_path, best_score = max(scored, key=lambda x: x[1])
    return best_path, best_score, dict(scored)


def find_project_root(start: str | Path | None = None, verbose: bool = False, weights: dict[str, int] | None = None, rel: bool = False) -> Path:
    """
    Heuristically find the project root directory.

    Walks up from the given start directory (or current working directory),
    scoring each ancestor based on common project markers (config files,
    VCS directories, env files, etc). Returns the directory with the
    highest score, breaking ties in favor of the directory closest to
    the starting point.

    If everything looks equally non-project-y, returns the starting directory.
    """
    best_path, best_score, scores = score_all(start, weights, rel=rel)
    if verbose:
        for k, v in scores.items():
            print(f"{'**' if k == best_path else ''} {v}: {k}")
    return best_path




def _parse_weight(s: str) -> tuple[str, int]:
    """Parse a weight string like 'pattern:value' or 'pattern=value'."""
    for sep in ("=", ":"):
        if sep in s:
            pattern, value = s.rsplit(sep, 1)
            return pattern, int(value)
    raise ValueError(f"Invalid weight format: {s!r} (expected 'pattern:value' or 'pattern=value')")


def main():
    import json

    parser = argparse.ArgumentParser(
        description="Heuristically detect the root of a project directory"
    )

    parser.add_argument(
        "start",
        nargs="?",              # makes it optional
        default=None,
        help="Optional starting directory. Defaults to current working directory.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print scoring results for all candidate directories",
    )

    parser.add_argument(
        "--rel",
        action="store_true",
        help="Print path relative to current working directory",
    )

    parser.add_argument(
        "-w", "--weight",
        action="append",
        metavar="PATTERN:VALUE",
        help="Add/override a weight (e.g. './Cargo.toml:100' or 'src=-50'). Can be repeated.",
    )

    parser.add_argument(
        "--weights-json",
        metavar="JSON",
        help='Weights as JSON string (e.g. \'{"./Cargo.toml": 100}\')',
    )

    parser.add_argument(
        "--weights-file",
        metavar="PATH",
        help="Path to JSON file containing weights",
    )

    parser.add_argument(
        "--no-defaults",
        action="store_true",
        help="Don't use default weights, only use explicitly provided weights",
    )

    args = parser.parse_args()

    # Build weights dict
    weights = {} if args.no_defaults else dict(WEIGHTS)

    # Load from file first
    if args.weights_file:
        with open(args.weights_file) as f:
            weights.update(json.load(f))

    # Then JSON string
    if args.weights_json:
        weights.update(json.loads(args.weights_json))

    # Then individual -w flags (highest priority)
    if args.weight:
        for w in args.weight:
            pattern, value = _parse_weight(w)
            weights[pattern] = value

    root = find_project_root(start=args.start, verbose=args.verbose, weights=weights, rel=args.rel)
    print(root)


if __name__ == "__main__":
    main()
