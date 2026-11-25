"""Step 8: run the eval set and print accuracy, escalation precision/recall and wrong-answer rate.

Usage (from the project root):
    python eval/run_eval.py --tag baseline
    python eval/run_eval.py --tag after_fix --verbose
    
Results are saved to eval/results_<tag>.json so you can compare before and after.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agent.agent import SupportAgent  # noqa: E402


def run_case(agent, case):
    session = agent.new_session()
    res = None
    for turn in case["turns"]:
        res = agent.respond(turn, session)
    reply = res.reply.lower()
    correct = res.action == case["expect"]
    if correct and case["expect"] == "answer":
        correct = all(k.lower() in reply for k in case.get("contains", []))
    if correct and any(a.lower() in reply for a in case.get("absent", [])):
        correct = False
    if correct and case.get("verified") and not (res.handoff and res.handoff["identity_verified"]):
        correct = False
    return {"id": case["id"], "cat": case["cat"], "question": " | ".join(case["turns"]),
            "expected": case["expect"], "actual": res.action, "category": res.category,
            "correct": correct, "reply": res.reply, "trace": res.trace}


def pct(n, d):
    return f"{100 * n / d:5.1f}%" if d else "  n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run")
    ap.add_argument("--file", default="questions.json")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cases = json.load(open(os.path.join(ROOT, "eval", "questions.json"), encoding="utf-8"))
    agent = SupportAgent()
    rows = [run_case(agent, c) for c in cases]

    # per-category accuracy
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["cat"]].append(r)
    print(f"\n{'category':14} {'cases':>5} {'correct':>8}")
    for cat, rs in by_cat.items():
        print(f"{cat:14} {len(rs):5d} {pct(sum(r['correct'] for r in rs), len(rs)):>8}")

    # headline metrics
    exp_ans = [r for r in rows if r["expected"] == "answer"]
    answered = [r for r in rows if r["actual"] == "answer"]
    tp = sum(1 for r in rows if r["expected"] == "handoff" and r["actual"] == "handoff")
    fp = sum(1 for r in rows if r["expected"] != "handoff" and r["actual"] == "handoff")
    fn = sum(1 for r in rows if r["expected"] == "handoff" and r["actual"] != "handoff")
    metrics = {
        "cases": len(rows),
        "overall_accuracy": sum(r["correct"] for r in rows) / len(rows),
        "answer_accuracy": sum(r["correct"] for r in exp_ans) / len(exp_ans),
        "over_escalation_rate": sum(1 for r in exp_ans if r["actual"] == "handoff") / len(exp_ans),
        "wrong_answer_rate": (sum(1 for r in answered if not r["correct"]) / len(answered)) if answered else 0,
        "unsafe_answers": sum(1 for r in answered if r["expected"] == "handoff"),
        "escalation_precision": tp / (tp + fp) if tp + fp else 0,
        "escalation_recall": tp / (tp + fn) if tp + fn else 0,
    }
    print("\n=== HEADLINE METRICS ===")
    print(f"Overall accuracy (right action + right content): {metrics['overall_accuracy']*100:5.1f}%  ({sum(r['correct'] for r in rows)}/{len(rows)})")
    print(f"Answer accuracy (answerable questions answered correctly): {metrics['answer_accuracy']*100:5.1f}%")
    print(f"Over-escalation rate (answerable but handed off): {metrics['over_escalation_rate']*100:5.1f}%")
    print(f"Wrong-answer rate (agent answered but was wrong): {metrics['wrong_answer_rate']*100:5.1f}%")
    print(f"Unsafe answers (should have escalated but answered): {metrics['unsafe_answers']}")
    print(f"Escalation precision: {metrics['escalation_precision']*100:5.1f}%   recall: {metrics['escalation_recall']*100:5.1f}%")

    failures = [r for r in rows if not r["correct"]]
    print(f"\n=== {len(failures)} FAILURES ===")
    for r in failures:
        print(f"#{r['id']:<3} [{r['cat']}] {r['question'][:60]}")
        print(f"      expected={r['expected']}  got={r['actual']}  {r['category']}")
        if r["actual"] == "answer" or args.verbose:
            print(f"      reply: {r['reply'][:110]}")
        if args.verbose:
            print(f"      trace: {' > '.join(r['trace'])}")

    out = os.path.join(ROOT, "eval", args.file)
    json.dump({"metrics": metrics, "rows": rows}, open(out, "w"), indent=2)
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()