"""Heuristically detect the root of a project directory"""
import argparse
import re
from pathlib import Path


# Heuristic weights for files that usually indicate a project root
FILE_WEIGHTS = {
    # Very strong signals
    "pyproject.toml": 40,      # Python
    "package.json": 40,        # Node / JS
    "Cargo.toml": 40,          # Rust
    "go.mod": 40,              # Go
    "composer.json": 30,       # PHP
    "Gemfile": 30,             # Ruby
    "mix.exs": 30,             # Elixir

    # Python-specific but common
    "requirements.txt": 25,
    "Pipfile": 25,
    "poetry.lock": 25,
    "setup.py": 25,

    # Mono-repo / tool configs
    "pnpm-lock.yaml": 15,
    "yarn.lock": 15,
    "package-lock.json": 15,
    "tsconfig.json": 10,
    "webpack.config.js": 10,
    "next.config.js": 10,
    "vite.config.js": 10,
    "vite.config.ts": 10,
    "angular.json": 10,

    # Infra / dev tooling
    "docker-compose.yml": 15,
    "Dockerfile": 10,
    "Makefile": 10,
    ".editorconfig": 5,

    # General project-ish files
    ".env": 10,
    ".env.local": 8,
    ".env.example": 8,
    ".gitignore": 5,
    "README": 5,
    "README.md": 5,
    "README.rst": 5,
    "LICENSE": 5,

    # Framework entrypoints (weak hints on their own)
    "manage.py": 5,   # Django
}

# Heuristic weights for subdirectories
DIR_WEIGHTS = {
    # Version control
    ".git": 30,
    ".hg": 10,
    ".svn": 10,

    # Typical code / build dirs
    "src": 10,
    "dist": 10,
    "build": 10,
    "lib": 5,
    "app": 5,
    "server": 5,
    "client": 5,
    "backend": 5,
    "frontend": 5,
    "packages": 5,

    # Weak hints
    ".vscode": 2,
    ".idea": 2,
}

# Penalties for directories that are *probably not* the project root
NAME_PENALTIES = {
    # Your explicit suggestions (and then some)
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
}

# Penalties applied if ANY *parent* directory name matches these patterns.
# Supports `*` wildcards (converted to regex).
PARENT_NAME_PENALTY_PATTERNS = {
    ".venv": -200,
    "venv": -200,
    "node_modules": -200,
    "*env": -100,           # matches 'env', '.env', 'myenv', etc.
    "__pycache__": -150,
    "*cache*": -50,         # generic cache-ish dirs
    "bin": -100,
}



def _compile_patterns(patterns: dict[str, int]) -> list[tuple[re.Pattern[str], int]]:
    r"""
    Convert wildcard patterns into compiled regexes.
    Supports:
      myfile*      => ^myfile.*$
      *.json       => ^.*\.json$
      file.name    => ^file\.name$
    """
    compiled: list[tuple[re.Pattern[str], int]] = []
    for pattern, weight in patterns.items():
        # escape literal characters first
        escaped = re.escape(pattern)
        # transform escaped wildcard into regex wildcard
        regex_str = "^" + escaped.replace(r"\*", ".*") + "$"
        compiled.append((re.compile(regex_str), weight))
    return compiled


FILE_REGEXES = _compile_patterns(FILE_WEIGHTS)
DIR_REGEXES = _compile_patterns(DIR_WEIGHTS)
NAME_REGEXES = _compile_patterns(NAME_PENALTIES)
PARENT_REGEXES = _compile_patterns(PARENT_NAME_PENALTY_PATTERNS)


def _apply_matches(name: str, patterns: list[tuple[re.Pattern[str], int]]) -> int:
    """Return sum of weights for any regex matching given name."""
    total = 0
    for regex, weight in patterns:
        if regex.match(name):
            total += weight
    return total


def _parent_penalty(path: Path) -> int:
    """Apply penalties if ANY parent matches wildcard-aware patterns."""
    total = 0
    for parent in path.parents:
        total += _apply_matches(parent.name, PARENT_REGEXES)
    return total


def _score_directory(path: Path) -> int:
    """
    Assign a heuristic score based on:
      - root name
      - immediate children files/dirs
      - parent folder ancestry
    """
    score = 0

    # Penalize directory name if applicable
    score += _apply_matches(path.name, NAME_REGEXES)

    # Penalize entire ancestry
    score += _parent_penalty(path)

    # Check children files and dirs
    try:
        for child in path.iterdir():
            if child.is_file():
                score += _apply_matches(child.name, FILE_REGEXES)
            elif child.is_dir():
                score += _apply_matches(child.name, DIR_REGEXES)
    except Exception:
        pass

    return score


def score_all(start: str | Path | None = None):
    # Collect candidates the same way find_project_root would
    start= Path(start).expanduser().resolve() if start is not None else Path.cwd()
    candidates = [start] + list(start.parents)

    scored = [(path, _score_directory(path)) for path in candidates]
    best_path, best_score = max(scored, key=lambda x: x[1])
    return best_path, best_score, dict(scored)

def find_project_root(start: str | Path | None = None, verbose: bool = False) -> Path:
    """
    Heuristically find the project root directory.

    Walks up from the given start directory (or current working directory),
    scoring each ancestor based on common project markers (config files,
    VCS directories, env files, etc). Returns the directory with the
    highest score, breaking ties in favor of the directory closest to
    the starting point.

    If everything looks equally non-project-y, returns the starting directory.
    """
    best_path, best_score, scores = score_all(start)
    if verbose:
        for k, v in scores.items():
            print(f"{'**' if k == best_path else ''} {v}: {k}")
    return best_path


def main():
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

    args = parser.parse_args()

    start_path = Path(args.start).resolve() if args.start else Path.cwd()
    root = find_project_root(start=start_path, verbose=args.verbose)

    if args.rel:
        import os
        root = os.path.relpath(root, Path.cwd())

    print(root)


if __name__ == "__main__":
    main()
