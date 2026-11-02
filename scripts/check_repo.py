"""Read-only file policy/YAML check. No Git writes, remote calls or secret scanning."""

import argparse
import subprocess
from pathlib import Path, PurePosixPath

MAX_BYTES = 5 * 1024**2  # Repo policy for source/docs, not a GitHub service limit.
PRIVATE_ROOTS = {"data", "artifacts", "cache", "reports"}
BLOCKED_SUFFIXES = {".safetensors", ".ckpt", ".pt", ".pth", ".db", ".sqlite", ".log"}


def file_problem(name: str, size: int) -> str | None:
    path = PurePosixPath(name.replace("\\", "/"))
    parts = [p.casefold() for p in path.parts]
    leaf = path.name.casefold()
    if not parts or path.is_absolute() or ".." in parts:
        return "invalid repository path"
    if leaf.startswith(".env") and leaf != ".env.example":
        return "environment file must stay local"
    if any(p == ".venv" or p.startswith(".venv-") or p == "__pycache__" for p in parts):
        return "environment/cache must stay local"
    if parts[0] in PRIVATE_ROOTS:
        if parts[:2] == ["artifacts", "models"] or leaf not in {"readme.md", ".gitkeep"}:
            return "private payload must stay local"
    if path.suffix.casefold() in BLOCKED_SUFFIXES or ".sqlite-" in leaf:
        return "model/database/log payload must stay local"
    if size > MAX_BYTES:
        return "exceeds 5 MiB source/docs policy; review storage before committing"
    return None


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout


def candidates(root: Path, *, staged: bool) -> list[tuple[str, int]]:
    args = (
        ("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
        if staged
        else ("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    )
    paths = sorted({p.decode("utf-8") for p in git(root, *args).split(b"\0") if p})
    rows = []
    for name in paths:
        # Inspect index size, not the worktree copy, for a staged commit.
        if staged:
            size = int(git(root, "cat-file", "-s", ":" + name).strip())
        elif (root / name).is_file():
            size = (root / name).stat().st_size
        else:
            continue  # A tracked deletion has no new payload to inspect.
        rows.append((name, size))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged", action="store_true", help="Check only added/modified index files"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    rows = candidates(root, staged=args.staged)
    if args.staged and not rows:
        print("No staged added/modified files. Stage manually, then run this check again.")
        raise SystemExit(2)
    problems = [(name, reason) for name, size in rows if (reason := file_problem(name, size))]
    for name, reason in problems:
        print(f"FAIL {name}: {reason}")
    if not args.staged:
        import yaml

        for name, _ in rows:
            if PurePosixPath(name).suffix.lower() in {".yaml", ".yml"} and not file_problem(
                name, 0
            ):
                try:
                    parsed = yaml.safe_load((root / name).read_text(encoding="utf-8"))
                    if not isinstance(parsed, dict):
                        raise ValueError("expected a YAML mapping")
                except (ValueError, yaml.YAMLError) as exc:
                    # Do not echo YAML contents or potentially sensitive values.
                    print(f"FAIL {name}: invalid YAML ({type(exc).__name__})")
                    problems.append((name, "invalid YAML"))
    if problems:
        raise SystemExit(1)
    print(f"PASS: {len(rows)} {'staged' if args.staged else 'candidate'} files; name/size policy.")
    if not args.staged:
        print("Worktree YAML syntax checked.")
    print("Not a secret/content/license review. No Git state changed.")


if __name__ == "__main__":
    main()
