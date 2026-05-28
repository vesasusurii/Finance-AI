"""Verify refactored prompts match legacy monolithic output."""
from __future__ import annotations

import argparse
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
BASELINE = BACKEND / "_prompt_baseline.txt"

import sys

sys.path.insert(0, str(BACKEND))


def serialize_prompts(vision: str, batch: str, merge: str) -> str:
    return f"VISION\n{vision}\n\nBATCH\n{batch}\n\nMERGE\n{merge}"


def load_legacy_from_baseline() -> tuple[str, str, str]:
    if not BASELINE.exists():
        raise SystemExit(
            f"Missing prompt baseline: {BASELINE}\n"
            "If the current prompts are the intended baseline, run:\n"
            "  python scripts/prompts/verify_prompt_refactor.py --write-baseline\n"
            "Then run the verifier again."
        )
    text = BASELINE.read_text(encoding="utf-8")
    parts = text.split("\n\nBATCH\n", 1)
    vision = parts[0].removeprefix("VISION\n")
    rest = parts[1].split("\n\nMERGE\n", 1)
    return vision, rest[0], rest[1]


def write_baseline(vision: str, batch: str, merge: str) -> None:
    BASELINE.write_text(serialize_prompts(vision, batch, merge), encoding="utf-8")
    print(f"Wrote prompt baseline: {BASELINE}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Capture the currently assembled prompts as _prompt_baseline.txt.",
    )
    args = parser.parse_args()

    from ai.prompts import BATCH_SYSTEM_PROMPT, MERGE_SYSTEM_PROMPT, VISION_SYSTEM_PROMPT

    if args.write_baseline:
        write_baseline(VISION_SYSTEM_PROMPT, BATCH_SYSTEM_PROMPT, MERGE_SYSTEM_PROMPT)
        return

    old_v, old_b, old_m = load_legacy_from_baseline()
    checks = [
        ("VISION", old_v, VISION_SYSTEM_PROMPT),
        ("BATCH", old_b, BATCH_SYSTEM_PROMPT),
        ("MERGE", old_m, MERGE_SYSTEM_PROMPT),
    ]
    failed = False
    for name, old, new in checks:
        if old == new:
            print(f"{name}: OK ({len(new)} chars)")
        else:
            failed = True
            print(f"{name}: MISMATCH (old {len(old)} vs new {len(new)})")
            # First diff position
            for i, (a, b) in enumerate(zip(old, new)):
                if a != b:
                    print(f"  first diff at {i}: {a!r} vs {b!r}")
                    print(f"  old context: {old[max(0,i-40):i+40]!r}")
                    print(f"  new context: {new[max(0,i-40):i+40]!r}")
                    break
            if len(old) != len(new):
                print(f"  length delta: {len(new) - len(old)}")
    if failed:
        raise SystemExit(1)
    print("All prompts byte-identical to baseline.")


if __name__ == "__main__":
    main()
