"""Score annotated PR review benchmark runs with exact issue-label matching.

Input predictions must be adjudicated to stable issue IDs from the case
annotations. The scorer deliberately does not infer whether two prose findings
mean the same thing.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def score_run(cases: list[dict[str, Any]], system: str) -> dict[str, Any]:
    counts = Counter(tp=0, fp=0, fn=0, verified=0, predicted=0, citations_correct=0, citations=0)
    durations: list[float] = []
    completed_cases = 0

    for case in cases:
        result = case.get("systems", {}).get(system)
        if not result or result.get("status") != "measured":
            continue
        gold = set(case.get("gold_issue_ids", []))
        predictions = result.get("predicted_issue_ids", [])
        predicted = set(predictions)
        if len(predicted) != len(predictions):
            raise ValueError(f"Duplicate predicted issue id in {case.get('case_id')} / {system}")
        counts["tp"] += len(gold & predicted)
        counts["fp"] += len(predicted - gold)
        counts["fn"] += len(gold - predicted)
        counts["predicted"] += int(result.get("finding_count", len(predicted)))
        counts["verified"] += int(result.get("verified_prediction_count", 0))
        counts["citations_correct"] += int(result.get("citation_correct_count", 0))
        counts["citations"] += int(result.get("citation_count", 0))
        if "elapsed_seconds" in result:
            durations.append(float(result["elapsed_seconds"]))
        completed_cases += 1

    precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else None
    recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else None
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else None
    verification_rate = counts["verified"] / counts["predicted"] if counts["predicted"] else None
    citation_accuracy = counts["citations_correct"] / counts["citations"] if counts["citations"] else None

    return {
        "system": system,
        "measured_cases": completed_cases,
        "tp": counts["tp"],
        "fp": counts["fp"],
        "fn": counts["fn"],
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "evidence_verification_rate": verification_rate,
        "citation_accuracy": citation_accuracy,
        "mean_elapsed_seconds": sum(durations) / len(durations) if durations else None,
        "timed_cases": len(durations),
    }


def score_benchmark(data: dict[str, Any]) -> list[dict[str, Any]]:
    cases = data.get("cases", [])
    systems = sorted({name for case in cases for name in case.get("systems", {})})
    return [score_run(cases, system) for system in systems]


def render_markdown(data: dict[str, Any], results: list[dict[str, Any]]) -> str:
    labels = {
        "prism_gemini": "PRism (Gemini)",
        "unstructured_gemini": "Unstructured Gemini",
    }
    lines = [
        f"# {data.get('title', 'PRism review benchmark')}",
        "",
        str(data.get("scope_note", "")),
        "",
        "| System | Cases | Precision | Recall | F1 | Evidence verified | Citation accuracy | Mean time |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        fmt = lambda value: "—" if value is None else f"{value:.1%}"
        elapsed = "—" if row["mean_elapsed_seconds"] is None else f"{row['mean_elapsed_seconds']:.2f}s"
        lines.append(
            f"| {labels.get(row['system'], row['system'])} | {row['measured_cases']} | {fmt(row['precision'])} | "
            f"{fmt(row['recall'])} | {fmt(row['f1'])} | "
            f"{fmt(row['evidence_verification_rate'])} | {fmt(row['citation_accuracy'])} | {elapsed} |"
        )
    lines.extend(["", "## Counts", "", "| System | TP | FP | FN | Timed cases |", "|---|---:|---:|---:|---:|"])
    for row in results:
        lines.append(f"| {labels.get(row['system'], row['system'])} | {row['tp']} | {row['fp']} | {row['fn']} | {row['timed_cases']} |")
    lines.extend(["", "Metrics use exact, adjudicated issue IDs per case. Missing systems and timing data are omitted, not imputed.", ""])
    lines.extend([str(note) for note in data.get("notes", [])])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="JSON benchmark run file")
    parser.add_argument("--markdown", type=Path, help="Write a Markdown summary")
    args = parser.parse_args()
    data = json.loads(args.results.read_text())
    results = score_benchmark(data)
    if args.markdown:
        args.markdown.write_text(render_markdown(data, results))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
