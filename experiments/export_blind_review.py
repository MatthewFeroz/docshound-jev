"""Prepare local review packets from saved inputs, without model verdicts."""

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def export(source: Path, output: Path) -> None:
    # Never overwrite a person's existing review work.
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    for path in sorted(source.glob("*/runs/*/run.json")):
        state = json.loads(path.read_text(encoding="utf-8"))
        for index, finding in enumerate(state["clusters"]):
            cases.append((state, index, finding))
    random.Random(20260919).shuffle(cases)
    labels, key = [], []
    for number, (state, index, finding) in enumerate(cases, start=1):
        review_id = f"case-{number:03d}"
        triage = json.loads(finding["jev_triage"]["request"]["state"])
        evidence = json.loads(finding["jev_assessment"]["request"]["state"])
        packet = {
            "review_id": review_id,
            "repo": state["repo"],
            "triage_input": triage,
            "evidence_input": evidence,
        }
        (output / f"{review_id}.json").write_text(
            json.dumps(packet, indent=2), encoding="utf-8"
        )
        lines = [
            f"# {review_id}: {finding['name']}",
            "",
            f"Repository: {state['repo']}",
            "",
            finding["summary"],
            "",
            f"Question: {finding['recurring_question']}",
            "",
            "## Original activity supplied to Jev",
            "",
        ]
        for item in triage["source_activity"]:
            lines.extend(
                [
                    f"### #{item['number']}: {item['title']}",
                    "",
                    item["url"],
                    "",
                    f"Recorded state: {item['state']}; updated: {item.get('updated_at')}",
                    "",
                    item.get("body") or "No body supplied.",
                    "",
                ]
            )
        lines.extend(["## Retrieved excerpts supplied to Jev", ""])
        for i, doc in enumerate(evidence["candidate_docs"], start=1):
            lines.extend(
                [
                    f"### Passage {i}: {doc['path']}",
                    "",
                    doc["url"],
                    "",
                    doc["content"],
                    "",
                ]
            )
        lines.extend(
            [
                "## Your review (before opening the answer key)",
                "",
                "- Is the claimed behavior established by the supplied evidence? established / unverified / conflicting / unknown",
                "",
                "- Does the supplied documentation answer the question? answered / partial / absent from supplied passages / unknown",
                "",
                "- Is drafting justified now? yes / no / unknown",
                "",
                "- Passage relevance (each): direct answer / useful background / unrelated / unknown",
                "",
                "- Evidence and rationale:",
                "",
                "- Additional pinned source inspection (record separately):",
                "",
            ]
        )
        (output / f"{review_id}.md").write_text("\n".join(lines), encoding="utf-8")
        labels.append(
            {
                "review_id": review_id,
                "reviewer": None,
                "readiness": None,
                "documentation_coverage": None,
                "drafting_justified": None,
                "passage_relevance": [None] * len(evidence["candidate_docs"]),
                "rationale": None,
                "additional_evidence": None,
            }
        )
        key.append(
            {
                "review_id": review_id,
                "case_id": f"{state['run_id']}:{index}",
                "finding": finding["name"],
                "luna_coverage": finding["documentation_coverage"],
                "jev_triage": finding["jev_triage"]["answers"],
                "jev_review": finding["jev_assessment"]["answers"],
                "recommendation": finding["jev_assessment"]["recommendation"],
                "held": bool(finding["jev_draft_hold"]),
                "drafted": bool(finding["draft_markdown"]),
            }
        )
    for name, records in [("review-labels.jsonl", labels), ("answer-key.jsonl", key)]:
        (output / name).write_text(
            "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
        )
    (output / "README.md").write_text(
        "# Blind review packets\n\n"
        "Read the numbered Markdown packets and fill review-labels.jsonl before opening answer-key.jsonl. "
        "The packets preserve Jev's original input snapshots, including source-text truncation and retrieved excerpts, "
        "but omit classifier outputs, Luna coverage verdicts and the hold/draft outcome. "
        "The candidate finding itself was generated by Luna; this is not independent discovery of findings.\n\n"
        "All review labels are blank. Allow unknown; absence from three excerpts does not prove corpus-wide absence. "
        "Record any extra source inspection separately from the input-only judgment. "
        "The original full run artifacts retain generated drafts for a later output-quality review.\n",
        encoding="utf-8",
    )
    print(f"Prepared {len(cases)} unlabeled packets: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=ROOT / "experiments/results/cross-repository"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments/results/blind-review"
    )
    args = parser.parse_args()
    export(args.source, args.output)
