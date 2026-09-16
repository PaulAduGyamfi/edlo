"""
An eval is a release gate, not a report card. Its output is pass or
RELEASE BLOCKED.

Cases carry canned model output, so the suite exercises the deterministic
wall (grounding, merge, policy) offline and free. Hard gates are set from
consequences: a fabricated quote guiding a public edit is unrecoverable, so
grounding is 100% or the release is blocked. Soft metrics are tracked and
compared, never gated.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from edlo.ai.grounding import merge, normalize, validate
from edlo.ai.schemas import Candidate, ColdOpenCandidate
from edlo.config import get_settings
from edlo.services.policy import check_pack
from edlo.transcription.schema import TranscriptArtifact

CASES = Path("evals/cases")
REPORTS = Path("proof/evals")

# 100% or the release is blocked.
HARD_GATES = {
    "grounded_quotes": 1.0,
    "quotes_at_cited_timecode": 1.0,
    "human_flags_preserved": 1.0,
    "timecodes_in_range": 1.0,
    "cut_cap_respected": 1.0,
    "no_invented_links_or_sponsors": 1.0,
}
SOFT_CHECKS = ("expected_rejections", "expected_kept_cuts", "expected_cold_opens")


@dataclass
class Flag:
    id: str
    start_ms: int
    end_ms: int
    note: str | None


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001 - no git is fine for a report
        return "unknown"


def dataset_version(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def run_case(
    case: dict[str, Any], *, max_cuts: int, max_cold_opens: int
) -> dict[str, bool | str]:
    t = TranscriptArtifact(
        audio_checksum="0" * 64,
        engine="eval",
        model_version="eval",
        language="en",
        **case["transcript"],
    )
    flags = [Flag(**f) for f in case["human_flags"]]
    cuts = [Candidate(**c) for c in case["model_cuts"]]
    colds = [ColdOpenCandidate(**c) for c in case["model_cold_opens"]]
    expect = case.get("expect", {})

    items, rejected = merge(flags, cuts, t, cap=max_cuts)
    kept_colds, rejected_colds = validate(
        colds, t, max_items=max_cold_opens, max_span_ms=60_000
    )
    model_items = [i for i in items if i.source == "model"]
    full = normalize(" ".join(s.text for s in t.segments))
    rules = Counter(r.rule for r in rejected + rejected_colds)

    checks: dict[str, bool | str] = {}
    # Independent re-verification of what survived, not trust in validate().
    checks["grounded_quotes"] = all(
        normalize(i.quote) in full for i in model_items
    ) and all(normalize(c.exact_quote) in full for c in kept_colds)
    checks["quotes_at_cited_timecode"] = all(
        normalize(i.quote)
        in normalize(t.text_between(i.start_ms - 2000, i.end_ms + 2000))
        for i in model_items
    ) and all(
        normalize(c.exact_quote)
        in normalize(t.text_between(c.start_ms - 2000, c.end_ms + 2000))
        for c in kept_colds
    )
    checks["human_flags_preserved"] = {
        i.flag_id for i in items if i.source == "human"
    } == {f.id for f in flags}
    checks["timecodes_in_range"] = all(
        0 <= i.start_ms < i.end_ms <= t.duration_ms for i in items
    ) and all(0 <= c.start_ms < c.end_ms <= t.duration_ms for c in kept_colds)
    checks["cut_cap_respected"] = (
        len(items) <= max(max_cuts, len(flags)) and len(kept_colds) <= max_cold_opens
    )
    pack = case.get("pack")
    violations = (
        check_pack(
            links=pack["links"],
            sponsors=pack["sponsors"],
            chapters=pack["chapters"],
            transcript_text=" ".join(s.text for s in t.segments),
        )
        if pack
        else []
    )
    # The gate is that policy CATCHES what the case plants, and nothing planted gets through.
    planted = set(expect.get("pack_violations", []))
    checks["no_invented_links_or_sponsors"] = {v.rule for v in violations} == planted

    if "rejected_rules" in expect:
        checks["expected_rejections"] = all(
            rules.get(k, 0) == v for k, v in expect["rejected_rules"].items()
        )
    if "kept_model_cuts" in expect:
        checks["expected_kept_cuts"] = len(model_items) == expect["kept_model_cuts"]
    if "kept_cold_opens" in expect:
        checks["expected_cold_opens"] = len(kept_colds) == expect["kept_cold_opens"]
    if "max_cold_open_confidence" in expect:
        checks["expected_cold_opens"] = checks.get("expected_cold_opens", True) and all(
            c.confidence <= expect["max_cold_open_confidence"] for c in kept_colds
        )
    checks["_rejections"] = json.dumps(dict(rules), sort_keys=True)
    return checks


def main(label: str, cases_dir: Path = CASES, reports_dir: Path = REPORTS) -> int:
    settings = get_settings()
    paths = sorted(cases_dir.glob("*.json"))
    per_check: dict[str, dict[str, int]] = defaultdict(
        lambda: {"passed": 0, "total": 0}
    )
    per_bucket: dict[str, dict[str, int]] = defaultdict(
        lambda: {"passed": 0, "total": 0}
    )
    failures: list[dict[str, str]] = []

    for p in paths:
        case = json.loads(p.read_text())
        checks = run_case(
            case, max_cuts=settings.max_cuts, max_cold_opens=settings.max_cold_opens
        )
        ok = True
        for name, passed in checks.items():
            if name.startswith("_"):
                continue
            per_check[name]["total"] += 1
            per_check[name]["passed"] += int(bool(passed))
            if not passed:
                ok = False
                failures.append(
                    {
                        "case": case["id"],
                        "bucket": case["bucket"],
                        "check": name,
                        "rejections": str(checks["_rejections"]),
                    }
                )
        per_bucket[case["bucket"]]["total"] += 1
        per_bucket[case["bucket"]]["passed"] += int(ok)

    rates = {
        k: (v["passed"] / v["total"] if v["total"] else 1.0)
        for k, v in per_check.items()
    }
    blocked = [
        k for k, threshold in HARD_GATES.items() if rates.get(k, 0.0) < threshold
    ]
    report: dict[str, Any] = {
        "label": label,
        # Without these FOUR fields a report is uncomparable -- you cannot
        # tell whether a change came from the prompt, the model, the dataset
        # or the code.
        "commit_sha": git_sha(),
        "dataset_version": dataset_version(paths),
        "model": settings.model_name or settings.model_provider,
        "prompt_versions": {
            "cutlist": settings.prompt_cutlist_version,
            "pack": settings.prompt_pack_version,
        },
        "cases": len(paths),
        "per_check": {
            k: {**v, "rate": round(rates[k], 4)} for k, v in per_check.items()
        },
        "per_bucket": dict(per_bucket),
        "failures": failures,
        "release_blocked": bool(blocked),
        "blocked_by": blocked,
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"{label}-{report['commit_sha'][:8]}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")

    print(
        f"evals: {len(paths)} cases, dataset {report['dataset_version']}, report {out}"
    )
    for k, v in report["per_check"].items():
        gate = " (gate)" if k in HARD_GATES else ""
        print(f"  {k:<32} {v['passed']:>3}/{v['total']:<3} {v['rate']:.0%}{gate}")
    for f in failures:
        print(
            f"  FAIL {f['case']} [{f['bucket']}] {f['check']} rejections={f['rejections']}"
        )
    if blocked:
        print(f"\nRELEASE BLOCKED by: {', '.join(blocked)}")
        return 1
    print("\npass")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="local")
    sys.exit(main(parser.parse_args().label))
