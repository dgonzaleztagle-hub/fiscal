"""Comprueba que una auditoría use exactamente el baseline LibreDTE fijado."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


REQUIRED_DOCUMENT_TYPES = {"33", "34", "39", "41", "52", "56", "61"}


def git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--libredte-path", required=True, type=Path)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(__file__).parents[1] / "comparison" / "baseline.json",
    )
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    matrix = set(baseline["document_matrix"])
    if matrix != REQUIRED_DOCUMENT_TYPES:
        raise SystemExit(
            f"Matriz incompleta: esperados {sorted(REQUIRED_DOCUMENT_TYPES)}, "
            f"obtenidos {sorted(matrix)}"
        )

    expected = baseline["libredte"]["commit"].lower()
    actual = git_output(args.libredte_path, "rev-parse", "HEAD").lower()
    dirty = bool(git_output(args.libredte_path, "status", "--porcelain"))
    report = {
        "ok": actual == expected and not dirty,
        "expected_commit": expected,
        "actual_commit": actual,
        "reference_worktree_dirty": dirty,
        "document_types": sorted(matrix, key=int),
        "authority_order": baseline["authority_order"],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
