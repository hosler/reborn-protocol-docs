#!/usr/bin/env python3
"""Fail when a documentation `file:line` citation points at a file that is gone.

These repos cite source by `path/to/file.py:123` throughout the docs. A refactor
in one repo silently invalidates every citation in another, because nothing
connects them. That is not hypothetical: splitting `gs1_client.py`,
`gs2_client.py` and `game/gs2_gui.py` into packages killed 64 citations at once,
and the docs kept describing bugs that were already fixed.

This script resolves every citation it can and fails on the ones that clearly
rot. A citation it cannot resolve unambiguously is reported, never failed --
a guard that cries wolf is a guard somebody turns off.

    python3 scripts/check_doc_citations.py            # check, exit 1 on rot
    python3 scripts/check_doc_citations.py --verbose  # also list what it skipped
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

#: Directory prefixes a citation may be written relative to. Order matters only
#: for reporting; a citation resolving under exactly one root is unambiguous.
#: These overlap on purpose: `.` contains the rest, and a citation may be
#: written relative to a repo root, a package root, or the checkout root. The
#: basename index dedupes by resolved path so the overlap does not make every
#: file look ambiguous.
PREFIX_ROOTS = (
    ".",
    "pyReborn",
    "pyReborn/pyreborn",
    "reborn-protocol",
    "reborn-protocol/reborn_protocol",
    "pygserver",
    "pygserver/pygserver",
    "GServer-v2",
    "GServer-v2/server",
    "Preagonal/FourPlay/quattroplay",
    "Preagonal",
)

#: Where the prose lives. Each entry is (repo-relative dir, glob).
DOC_SOURCES = (
    ("reborn-protocol-docs/docs", "**/*.md"),
    ("reborn-protocol-docs/docs", "**/*.rst"),
    ("reborn-protocol-docs", "README.md"),
    ("pyReborn", "*.md"),
    ("pyReborn/game_tester", "*.md"),
    ("reborn-protocol", "README.md"),
)

#: Never walk these: build output, vendored environments, caches.
SKIP_DIR_PARTS = frozenset({"_build", "out", "venv", "__pycache__", ".git", "node_modules"})

#: Only these extensions are treated as citable source.
SOURCE_SUFFIXES = frozenset({
    ".py", ".cpp", ".h", ".hpp", ".c", ".cc", ".txt", ".json", ".nw", ".gani",
    ".s_decomped", ".gs2", ".gs2bc", ".rs", ".js",
})

CITATION = re.compile(
    r"(?<![A-Za-z0-9_/.-])"
    r"([A-Za-z0-9_][A-Za-z0-9_./+-]*"
    r"\.(?:py|cpp|hpp|h|cc|c|txt|json|nw|gani|s_decomped|gs2bc|gs2|rs|js))"
    r":(\d+)(?:-(\d+))?"
)


def find_root(start: Path) -> Path | None:
    """Walk up from `start` until a directory holds the sibling repos."""
    for candidate in [start, *start.parents]:
        if (candidate / "pyReborn").is_dir() and (candidate / "reborn-protocol").is_dir():
            return candidate
    return None


def index_basenames(root: Path) -> dict[str, list[Path]]:
    """Map every source basename under the roots to the paths that carry it."""
    # One walk. PREFIX_ROOTS all live under `root`, so re-walking each of them
    # would only rediscover the same files at ~11x the cost.
    index: dict[str, set[Path]] = defaultdict(set)
    stack = [root.resolve()]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for path in entries:
            if path.name in SKIP_DIR_PARTS or path.name.startswith(".git"):
                continue
            if path.is_dir():
                if not path.is_symlink():
                    stack.append(path)
            elif path.suffix in SOURCE_SUFFIXES:
                index[path.name].add(path)
    return {name: sorted(paths) for name, paths in index.items()}


def line_count(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def resolve(cited: str, root: Path,
            basenames: dict[str, list[Path]]) -> tuple[str, Path | None, list[Path]]:
    """Return (verdict, path, candidates).

    Verdict is 'found' (path set), 'gone' (the file is missing outright), or
    'ambiguous' (candidates may be non-empty when a basename matched several
    files -- the caller can still rule the citation out on line count alone).
    """
    if "/" in cited:
        hits = sorted({(root / prefix / cited).resolve()
                       for prefix in PREFIX_ROOTS
                       if (root / prefix / cited).is_file()})
        if hits:
            return "found", hits[0], hits
        # A path rooted in a directory we index, that does not exist, is rot.
        head = cited.split("/", 1)[0]
        indexed_heads = {p.split("/", 1)[0] for p in PREFIX_ROOTS if p != "."}
        known = indexed_heads | {"pyreborn", "reborn_protocol", "game_tester", "pygserver",
                                 "server", "src", "include", "tests", "tools", "docs", "asm"}
        if head in known:
            return "gone", None, []
        return "ambiguous", None, []

    matches = basenames.get(cited, [])
    if len(matches) == 1:
        return "found", matches[0], matches
    return "ambiguous", None, matches


def iter_doc_files(root: Path):
    for rel_dir, pattern in DOC_SOURCES:
        base = root / rel_dir
        if not base.is_dir():
            continue
        for path in sorted(base.glob(pattern)):
            if SKIP_DIR_PARTS & set(path.relative_to(root).parts):
                continue
            if path.is_file():
                yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verbose", action="store_true",
                        help="list every citation this script could not resolve")
    parser.add_argument("--root", type=Path, default=None,
                        help="opengraal2 checkout root (default: discovered)")
    args = parser.parse_args()

    # Discover from this script's own location first. The hook runs from any of
    # the sibling repos, but the script always sits inside the checkout.
    root = (args.root
            or find_root(Path(__file__).resolve().parent)
            or find_root(Path.cwd().resolve()))
    if root is None:
        print("check_doc_citations: cannot locate the checkout root; skipping.", file=sys.stderr)
        return 0

    basenames = index_basenames(root)

    dead: list[str] = []
    stale_line: list[str] = []
    unresolved: list[str] = []
    checked = 0

    for doc in iter_doc_files(root):
        try:
            text = doc.read_text(errors="replace")
        except OSError:
            continue
        rel_doc = doc.relative_to(root)
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in CITATION.finditer(line):
                cited, start_s, _end_s = match.group(1), match.group(2), match.group(3)
                if "://" in line[: match.start()][-8:]:
                    continue
                checked += 1
                verdict, path, candidates = resolve(cited, root, basenames)
                where = f"{rel_doc}:{lineno}"
                start = int(start_s)
                if verdict == "gone":
                    dead.append(f"  {where}: `{cited}:{start_s}` -> file does not exist")
                elif verdict == "ambiguous":
                    # A basename matching several files is normally unresolvable.
                    # But if the cited line overruns EVERY candidate, no reading
                    # of the citation is valid, so it is rot regardless.
                    lengths = [line_count(c) for c in candidates]
                    if lengths and all(total and start > total for total in lengths):
                        stale_line.append(
                            f"  {where}: `{cited}:{start_s}` -> longest candidate "
                            f"has {max(lengths)} lines ({len(candidates)} files share "
                            f"this name)")
                    else:
                        unresolved.append(f"  {where}: `{cited}:{start_s}`")
                else:
                    total = line_count(path)
                    if total and start > total:
                        stale_line.append(
                            f"  {where}: `{cited}:{start_s}` -> only {total} lines")

    print(f"check_doc_citations: {checked} citations, "
          f"{len(dead)} dead, {len(stale_line)} past end-of-file, "
          f"{len(unresolved)} unresolved (not failed)")

    if dead:
        print("\nDEAD -- the cited file no longer exists:")
        print("\n".join(dead))
    if stale_line:
        print("\nPAST EOF -- the file exists but is shorter than the cited line:")
        print("\n".join(stale_line))
    if unresolved and args.verbose:
        print("\nUNRESOLVED -- ambiguous basename or a root this script does not index:")
        print("\n".join(unresolved))

    if dead or stale_line:
        print("\nFix the citation, or re-derive it from the current source.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
