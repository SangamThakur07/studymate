"""
Evaluation harness for the AI Study Assistant.

Run from the backend folder:
    python eval/run_eval.py
    python eval/run_eval.py --pdf path/to/your_notes.pdf     (questions + agent sections only)

Four experiments, each answering a question an examiner would ask:
  1. RETRIEVAL      Does the right passage come back?  (embeddings vs TF-IDF vs random)
  2. QUESTIONS      Are the generated MCQs well-formed and leak-free?
  3. GRADING        Does the score rank good > partial > wrong-topic > irrelevant?
  4. AGENT          Does the decision logic behave correctly on known student states?

Results are printed and saved to eval/RESULTS.md.
"""
import argparse
import json
import os
import re
import sys
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("LLM_PROVIDER", "mock")  # evaluation never needs a paid API

from app.tools.material_tools import extract_text_from_pdf          # noqa: E402
from app.tools.knowledge_tools import extract_keywords               # noqa: E402
from app.tools.mcq_tools import (generate_mcq_set, find_concept_fragments,   # noqa: E402
                                 _concept_regex)
from app.tools.topic_tools import extract_topics                      # noqa: E402
from app.tools.rag_tools import chunk_text, rank_texts, _embed       # noqa: E402
from app.tools.evaluation_tools import semantic_similarity, finalize_score, key_term_coverage   # noqa: E402

REPORT = []


def out(line=""):
    print(line)
    REPORT.append(line)


def norm(t):
    return re.sub(r"\s+", " ", t).strip().lower()


# --------------------------------------------------------------------------- 1. retrieval
def eval_retrieval(text, items):
    out("## 1. Retrieval quality")
    chunks = chunk_text(text)
    low = [norm(c) for c in chunks]
    out(f"{len(items)} hand-written questions, {len(chunks)} passages. "
        f"A hit means a passage containing the answer sentence was ranked in the top k.")
    out("'Original' questions reuse words from the notes; 'paraphrase' questions deliberately share almost "
        "none, which is where semantic matching should help.\n")
    for it in items:
        it["_gold"] = {i for i, c in enumerate(low) if norm(it["gold"]) in c}
    items = [it for it in items if it["_gold"]]
    vectors = _embed(chunks)

    def table(group, title):
        if not group:
            return
        out(f"**{title}** ({len(group)} questions)\n")
        out("| Method | Hit@1 | Hit@3 | MRR |")
        out("|---|---|---|---|")
        for method in ("embeddings", "tfidf", "hybrid"):
            if method in ("embeddings", "hybrid") and not vectors:
                out(f"| {method} | n/a | n/a | n/a |  (embedding model not available on this machine)")
                continue
            hit1 = hit3 = rr = 0
            for it in group:
                scores, _ = rank_texts(chunks, it["query"], vectors=vectors, method=method)
                order = sorted(range(len(chunks)), key=lambda i: -float(scores[i]))
                rank = next((r for r, i in enumerate(order, 1) if i in it["_gold"]), None)
                hit1 += rank == 1
                hit3 += rank is not None and rank <= 3
                rr += 1 / rank if rank else 0
            n = len(group)
            out(f"| {method} | {hit1/n:.0%} | {hit3/n:.0%} | {rr/n:.2f} |")
        b1 = mean(len(it["_gold"]) / len(chunks) for it in group)
        b3 = mean(min(1.0, 3 * len(it["_gold"]) / len(chunks)) for it in group)
        out(f"| random baseline | {b1:.0%} | {b3:.0%} | - |")
        out()

    table([it for it in items if not it.get("paraphrase")], "Original questions")
    table([it for it in items if it.get("paraphrase")], "Paraphrase stress set")


# --------------------------------------------------------------------------- 2. questions
def eval_questions(text):
    out("## 2. Generated question quality")
    topics = extract_topics(text, limit=12)
    out(f"Topics found automatically: {', '.join(topics)}\n")

    def run(use_history):
        """Simulate a student taking one test per topic, in order."""
        asked, results = set(), []
        for t in topics:
            qs = generate_mcq_set(t, text, topics, n=5, exclude=asked if use_history else None)
            results.append((t, qs))
            asked |= {q["question"] for q in qs}
        return results

    def check(results):
        total = valid = leak_a = leak_d = dup = 0
        seen = set()
        for _t, qs in results:
            for q in qs:
                total += 1
                opts, ok = q["options"], True
                ok = len(opts) == 4 and len(set(o.lower() for o in opts)) == 4 and q["correct_answer"] in opts
                body = q["question"].lower().split(":", 1)[-1]
                if q["question"].startswith("Fill in the blank"):
                    if _concept_regex(q["correct_answer"].lower()).search(body):
                        leak_a += 1; ok = False
                    if any(_concept_regex(o.lower()).search(body) for o in opts if o != q["correct_answer"]):
                        leak_d += 1; ok = False
                if q["question"] in seen:
                    dup += 1; ok = False
                seen.add(q["question"])
                valid += ok
        return total, valid, leak_a, leak_d, dup

    plain, hist = run(False), run(True)
    a, b = check(plain), check(hist)
    out("Student takes one test per topic, in order. 'History-aware' = the agent remembers answered questions.\n")
    out("| Metric | No history | History-aware |")
    out("|---|---|---|")
    out(f"| Questions generated | {a[0]} | {b[0]} |")
    out(f"| Well-formed and unique | {a[1]}/{a[0]} = {a[1]/max(a[0],1):.0%} | {b[1]}/{b[0]} = {b[1]/max(b[0],1):.0%} |")
    out(f"| Correct answer visible in the question | {a[2]} | {b[2]} |")
    out(f"| Wrong option visible in the question | {a[3]} | {b[3]} |")
    out(f"| Repeated questions across tests | {a[4]} | {b[4]} |")
    out(f"| Topics with a full 5-question test | {sum(len(q)>=5 for _,q in plain)}/{len(topics)} | {sum(len(q)>=5 for _,q in hist)}/{len(topics)} |")
    out("\nWhen a topic has fewer than 5 fresh questions, the live app tops the test up with review questions on related topics.\n")
    return topics


# --------------------------------------------------------------------------- 3. grading
def eval_grading(text, items):
    out("## 3. Written-answer grading")
    out("Each answer is compared with the best of the top 3 sentences about the topic in the student's own notes. "
        "Score = what the app shows (0-10) after calibration, a minimum-substance rule (fewer than 4 meaningful "
        "words) and a key-term rule (must mention some of the notes' key terms); both rules cap the score below "
        "the pass mark. An answer counts as correct at 6 or more.\n")
    emb = bool(_embed(["x"]))
    labels = ["good", "partial", "vague_long", "wrong", "irrelevant"]
    raw = {k: [] for k in labels}; scr = {k: [] for k in labels}; cov = {k: [] for k in labels}
    problems = []
    for it in items:
        refs = find_concept_fragments(it["topic"], text, strict=True)[:3]
        if not refs:
            continue
        for k in labels:
            if k in it:
                sims = [semantic_similarity(it[k], r) for r in refs]
                b = max(range(len(refs)), key=lambda i: sims[i])   # the sentence the answer most resembles
                sim = sims[b]
                sc, note = finalize_score(sim, it[k], it["topic"], refs[b])
                raw[k].append(sim); scr[k].append(sc)
                cov[k].append(key_term_coverage(it[k], refs[b], it["topic"])[0])
                if (k == "good") != (sc >= 6):
                    problems.append(f"- {it['topic']} / {k}: score {sc} (similarity {sim:.2f}{', ' + note if note else ''}) -> \"{it[k][:70]}\"")
    out(f"Similarity method used: **{'embeddings' if emb else 'word-overlap fallback (embedding model unavailable)'}**\n")
    out("| Answer type | Answers | Mean similarity | Mean key-term coverage | Mean score (0-10) | Counted as correct (>= 6) |")
    out("|---|---|---|---|---|---|")
    names = {"partial": "partial (very short)", "vague_long": "vague but long"}
    for k in labels:
        if scr[k]:
            out(f"| {names.get(k, k)} | {len(scr[k])} | {mean(raw[k]):.2f} | {mean(cov[k]):.2f} | {mean(scr[k]):.2f} | {sum(x >= 6 for x in scr[k])}/{len(scr[k])} |")
    copies = [finalize_score(1.0, refs0[0], it["topic"], refs0[0])[0] for it in items
              for refs0 in [find_concept_fragments(it["topic"], text, strict=True)[:1]] if refs0]
    out(f"\nVerbatim copies of the notes' own sentence counted as correct: {sum(c >= 6 for c in copies)}/{len(copies)} "
        "(pasting the notes is not an answer in your own words).")
    out("\nIdeal: good answers counted as correct; every other type not counted as correct.")
    out(f"\nMisgraded answers ({len(problems)}):" if problems else "\nMisgraded answers: none")
    for line in problems:
        out(line)
    out("\nCaution: the scale and thresholds were set after seeing these examples, so the pass rates are "
        "optimistic. Add your own examples to eval_set.json (written by someone other than the author) "
        "to test it fairly.")
    out()


# --------------------------------------------------------------------------- 4. agent
def eval_agent():
    out("## 4. Agent decision logic")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models import Student, Concept, MasteryScore
    from app.services.agent_service import decide_next_action
    from app.tools.mastery_tools import update_mastery, review_interval_days
    from datetime import datetime, timedelta

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def setup(concepts, mastery):
        db = Session()
        st = Student(name="t", subject="X")
        db.add(st); db.commit()
        for name, prereq in concepts:
            db.add(Concept(student_id=st.id, name=name, subject="X", prerequisites=prereq))
        for item in mastery:             # (name, score[, days since last practised]); order = order the agent sees them
            name, score = item[0], item[1]
            days_ago = item[2] if len(item) > 2 else 0
            db.add(MasteryScore(student_id=st.id, concept_name=name, score=score, attempts=1,
                                last_updated=datetime.utcnow() - timedelta(days=days_ago)))
        db.commit()
        return db, st.id

    chain = [("A", ""), ("B", "A"), ("C", "B")]
    results = []

    db, sid = setup(chain, [])
    d = decide_next_action(db, sid)
    results.append(("New student: starts at the foundation topic", d["action"] == "intervene" and d["concept"] == "A", d))

    db, sid = setup(chain, [("A", 90), ("B", 20)])
    d = decide_next_action(db, sid)
    results.append(("Strong prerequisite: teaches the weak topic itself", d["concept"] == "B", d))

    db, sid = setup(chain, [("B", 20), ("A", 30)])
    d = decide_next_action(db, sid)
    results.append(("Weak topic whose prerequisite is also weak: goes to the prerequisite", d["concept"] == "A", d))

    db, sid = setup(chain, [("A", 90), ("B", 85), ("C", 80)])
    d = decide_next_action(db, sid)
    results.append(("Everything mastered: advances", d["action"] == "advance", d))

    db, sid = setup(chain, [])
    for _ in range(4):
        update_mastery(db, sid, "A", 10.0)
    up = db.query(MasteryScore).filter_by(student_id=sid, concept_name="A").first().score
    update_mastery(db, sid, "A", 0.0)
    down = db.query(MasteryScore).filter_by(student_id=sid, concept_name="A").first().score
    results.append(("Mastery rises with correct answers and falls after a wrong one", up == 100 and down < up, {"after_4_correct": up, "after_1_wrong": down}))

    # --- spaced revision ---
    db, sid = setup(chain, [("A", 85, 10), ("B", 85, 1), ("C", 85, 0)])
    d = decide_next_action(db, sid)
    results.append(("Mastered topic not practised for 10 days: schedules a review of it",
                    d["action"] == "review" and d["concept"] == "A", d))

    db, sid = setup(chain, [("A", 85, 10), ("B", 30, 0)])
    d = decide_next_action(db, sid)
    results.append(("A weak topic takes priority over an overdue review",
                    d["action"] == "intervene" and d["concept"] == "B", d))

    db, sid = setup(chain, [("A", 85, 1), ("B", 85, 1), ("C", 85, 1)])
    d = decide_next_action(db, sid)
    results.append(("Mastered and practised yesterday (4-day interval): nothing due, advances",
                    d["action"] == "advance", d))

    db, sid = setup(chain, [("A", 85, 10), ("B", 85, 9), ("C", 85, 3)])
    d = decide_next_action(db, sid)
    results.append(("Several topics overdue: reviews the most overdue one first",
                    d["action"] == "review" and d["concept"] == "A", d))

    results.append(("Review intervals grow with mastery (50->1, 70->2, 85->4, 95->7 days)",
                    [review_interval_days(s) for s in (50, 70, 85, 95)] == [1, 2, 4, 7], None))

    out("| Test | Result |")
    out("|---|---|")
    for name, ok, detail in results:
        out(f"| {name} | {'PASS' if ok else 'FAIL'} |")
    out(f"\n{sum(1 for r in results if r[1])}/{len(results)} agent tests passed.\n")


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=os.path.join(HERE, "sample_notes.pdf"))
    args = ap.parse_args()
    data = json.load(open(os.path.join(HERE, "eval_set.json")))
    text = extract_text_from_pdf(open(args.pdf, "rb").read())

    out("# Evaluation results\n")
    out(f"Notes used: `{os.path.basename(args.pdf)}` ({len(text)} characters)\n")
    if os.path.basename(args.pdf) == "sample_notes.pdf":
        eval_retrieval(text, data["retrieval"])
    else:
        out("## 1. Retrieval quality\nSkipped: the hand-labelled questions are written for sample_notes.pdf.\n")
    eval_questions(text)
    if os.path.basename(args.pdf) == "sample_notes.pdf":
        eval_grading(text, data["grading"])
    eval_agent()
    open(os.path.join(HERE, "RESULTS.md"), "w", encoding="utf-8").write("\n".join(REPORT))
    print(f"\nSaved to {os.path.join(HERE, 'RESULTS.md')}")


if __name__ == "__main__":
    main()
