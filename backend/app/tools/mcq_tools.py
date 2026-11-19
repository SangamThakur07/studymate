"""
Extractive question generation from the student's OWN notes - no LLM needed.

Technique (classic NLP "cloze" generation):
  1. Retrieve the passage for the concept (RAG), split it into sentences.
  2. Find the sentence that defines the concept (concept appears at/near the start).
  3. Blank out the concept  ->  "_____ is the process of splitting text into tokens".
  4. Distractors = OTHER concepts extracted from the same notes, so wrong options
     are plausible, on-topic and come from the same document.

Also provides concept cleaning (drop generic words like "using", "called") and
find_definition_sentence(), reused as the reference answer when grading written
answers, so answers are compared against the student's own notes.
"""
import random
import re

# Verbs/participles: a topic name is a noun phrase, so a phrase containing any of these is not a topic.
VERBS = {
    "using", "used", "use", "uses", "called", "call", "based", "produce", "produces", "produced",
    "allow", "allows", "allowed", "measure", "measures", "represent", "represents", "learn", "learns",
    "learned", "compute", "computes", "computed", "depend", "depends", "handle", "handles", "improve",
    "improves", "improved", "operate", "operates", "reduce", "reduces", "reduced", "return", "returns",
    "choose", "chooses", "apply", "applied", "applies", "turn", "turns", "become", "becomes", "provide",
    "provides", "contain", "contains", "include", "includes", "require", "requires", "perform",
    "performs", "enable", "enables", "give", "gives", "take", "takes", "find", "finds", "show", "shows",
    "let", "lets", "get", "gets", "help", "helps", "run", "runs", "lie", "lies", "happen", "happens",
    "matter", "matters", "make", "makes", "making", "need", "needs", "like", "chop", "chops", "split",
    "splits", "work", "works", "see", "sees", "say", "says", "mean", "means",
}

# Words too vague to be a topic ON THEIR OWN ('word', 'text'); fine inside a real phrase
# ('word embeddings', 'text classification').
GENERIC_WORDS = {
    "base", "also", "such", "often", "usually", "first", "step", "steps", "kind", "type", "types",
    "form", "forms", "way", "ways", "thing", "things", "part", "parts", "set", "number", "unit",
    "units", "text", "word", "words", "notes", "study", "example", "examples", "important",
    "different", "common", "simple", "end", "ends", "case", "cases", "quickly", "easily", "rather",
    "even", "much", "many", "most", "each", "every", "other", "close", "input", "output", "vector",
    "process", "processing", "stage", "stages", "method", "methods", "quality",
}

# Evaluative adjectives that only decorate a topic ('good tokenization').
FILLER = {"good", "better", "best", "bad", "main", "key", "basic", "useful", "important", "simple", "common"}


def is_good_concept(term: str) -> bool:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS as STOP

    t = term.strip().lower()
    if len(t) < 4:
        return False
    toks = t.split()
    if any(not re.fullmatch(r"[a-z][a-z0-9\-]*", tok) for tok in toks):
        return False
    if toks[0] in STOP or toks[-1] in STOP:
        return False
    if any(tok in VERBS for tok in toks) or toks[-1].endswith("ly"):
        return False
    if len(toks) == 1 and toks[0] in GENERIC_WORDS:
        return False
    if len(toks) > 1 and (all(tok in GENERIC_WORDS for tok in toks) or toks[0] in FILLER):
        return False
    return True


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())


def _concept_regex(concept: str):
    words = [re.escape(w) for w in concept.split()]
    return re.compile(r"\b" + r"\s+".join(words) + r"(?:s|es)?\b", re.IGNORECASE)


def find_concept_fragments(concept: str, text: str, strict: bool = False) -> list[str]:
    """All usable sentences about `concept`, best first (definition-style sentences rank
    highest). PDF run-together headings ('Tokenization Tokenization is ...') are trimmed and
    a sentence is never cut short.

    strict=True  -> only sentences where the concept opens the sentence (<=1 word before it).
    strict=False -> also sentences that merely mention it (6-45 words, not title lines).
    """
    rx = _concept_regex(concept)
    scored = []
    for sent in _sentences(text):
        ms = list(rx.finditer(sent))
        if not ms:
            continue
        start = 0
        if len(ms) >= 2 and ms[1].start() - ms[0].end() <= 6:  # heading echoed by the body
            start = ms[1].start()
        frag = sent[start:].strip()
        n = len(frag.split())
        if n < 6 or n > 45 or " - " in frag:  # " - " = title/heading line, never a good question
            continue
        m = rx.search(frag)
        words_before = len(frag[:m.start()].split())
        if words_before <= 1:
            score = 3 - words_before          # 3 = opens the sentence, 2 = one word before
        elif strict:
            continue
        else:
            score = 1
        scored.append((score, frag))
    scored.sort(key=lambda x: -x[0])          # stable: keeps document order within a tier
    out, seen = [], set()
    for _score, frag in scored:
        if frag not in seen:
            seen.add(frag)
            out.append(frag)
    return out


def concept_definition_score(concept: str, text: str) -> int:
    """How strongly the notes DEFINE this concept: 3 = a sentence opens with it,
    2 = it follows one word ('Word embeddings represent...'), 1 = only mentioned, 0 = absent."""
    rx = _concept_regex(concept)
    best = 0
    for frag in find_concept_fragments(concept, text, strict=False):
        m = rx.search(frag)
        wb = len(frag[:m.start()].split())
        best = max(best, 3 - wb if wb <= 1 else 1)
    return best


def find_definition_sentence(concept: str, text: str, strict: bool = True):
    """Best single sentence explaining `concept` (used as the grading reference)."""
    frags = find_concept_fragments(concept, text, strict=strict)
    return frags[0] if frags else None


def clean_concepts(keywords: list[str], text: str, limit: int = 12) -> list[str]:
    """Keep real, quiz-able topics: drop generic words, merge duplicates/plurals, drop a
    short concept when a longer one contains it, and prefer topics the notes actually
    DEFINE (so every topic can produce a good question)."""
    low_text = text.lower()
    seen, kept = set(), []
    for k in keywords:
        t = k.strip().lower()
        if not is_good_concept(t) or t not in low_text:
            continue
        key = t[:-1] if t.endswith("s") and len(t) > 4 else t
        if key in seen:
            continue
        seen.add(key)
        kept.append(t)
    # Overlapping candidates ('tokenization' vs 'tokenization improves' vs 'good tokenization'):
    # keep whichever the notes DEFINE more strongly. On a tie keep the longer, more specific
    # phrase only if the short term mostly occurs inside it; otherwise keep the short term.
    def occurrences(term):
        return len(_concept_regex(term).findall(text))

    for t in list(kept):
        for o in list(kept):
            if o == t or t not in kept or o not in kept or not re.search(rf"\b{re.escape(t)}", o):
                continue
            st, so = concept_definition_score(t, text), concept_definition_score(o, text)
            if st > so:
                kept.remove(o)
            elif so > st:
                kept.remove(t)
            elif occurrences(o) >= 0.5 * occurrences(t):
                kept.remove(t)
            else:
                kept.remove(o)

    defined = [t for t in kept if find_definition_sentence(t, text, strict=True)]
    others = [t for t in kept if t not in defined and find_definition_sentence(t, text, strict=False)]
    chosen = defined if len(defined) >= 4 else defined + others
    # A topic mentioned in only one sentence cannot support a test; drop it when enough remain.
    supported = [t for t in chosen if len(find_concept_fragments(t, text, strict=False)) >= 2]
    if len(supported) >= 4:
        chosen = supported
    return chosen[:limit]


def _display(s: str) -> str:
    return s[:1].upper() + s[1:]


def generate_cloze_mcq(concept: str, text: str, pool: list[str]):
    """Fill-in-the-blank MCQ from the notes, or None if no good sentence/distractors."""
    frag = find_definition_sentence(concept, text, strict=True) or \
        find_definition_sentence(concept, text, strict=False)
    if not frag:
        return None
    rx = _concept_regex(concept)
    blanked = rx.sub("_____", frag)
    if "_____" not in blanked or rx.search(blanked):
        return None

    cl = concept.lower()
    seen, cands = {cl}, []
    for p in pool:
        pl = p.strip().lower()
        if pl in seen or pl in cl or cl in pl or not is_good_concept(pl):
            continue
        seen.add(pl)
        cands.append(p.strip())
    rng = random.Random(f"{concept}|{frag}")
    rng.shuffle(cands)
    if len(cands) < 3:
        return None

    options = [_display(concept)] + [_display(d) for d in cands[:3]]
    rng.shuffle(options)
    return {
        "question": f"Fill in the blank: {blanked}",
        "options": options,
        "correct_answer": _display(concept),
    }


# ---------------------------------------------------------------------------
# Multi-question tests: several different MCQs for ONE topic
# ---------------------------------------------------------------------------

def _related(a: str, b: str) -> bool:
    a, b = a.lower(), b.lower()
    return a == b or a in b or b in a


def _pick_distractors(pool, answer, visible_text, rng, k=3):
    """Wrong options: other topics from the notes that do NOT already appear in the
    question text (a visible word can't be a plausible wrong answer)."""
    vis = visible_text.lower()
    cands, seen = [], set()
    for p in pool:
        pl = p.strip().lower()
        if pl in seen or _related(pl, answer) or not is_good_concept(pl):
            continue
        if _concept_regex(pl).search(vis):
            continue
        seen.add(pl)
        cands.append(p.strip())
    rng.shuffle(cands)
    return cands[:k] if len(cands) >= k else None


def _cloze_question(frag: str, term: str, pool: list[str]):
    rx = _concept_regex(term)
    blanked = rx.sub("_____", frag)
    if "_____" not in blanked or rx.search(blanked):
        return None
    rng = random.Random(f"{term}|{frag}")
    d = _pick_distractors(pool, term, blanked, rng)
    if not d:
        return None
    options = [_display(term)] + [_display(x) for x in d]
    rng.shuffle(options)
    return {"question": f"Fill in the blank: {blanked}", "options": options,
            "correct_answer": _display(term)}


def _is_singular(predicate: str) -> bool:
    w = predicate.split()[0].lower()
    return w in ("is", "has") or (w.endswith("s") and w not in ("are", "have"))


def _predicate_question(concept: str, text: str, pool: list[str]):
    """'Complete the sentence: "Tokenization ..."' with the right continuation among
    continuations of other topics (matched for singular/plural so grammar gives no clue)."""
    strict = find_concept_fragments(concept, text, strict=True)
    if not strict:
        return None
    frag = strict[0]
    m = _concept_regex(concept).search(frag)
    stem, pred = frag[:m.end()].strip(), frag[m.end():].strip()
    if len(pred.split()) < 4:
        return None
    flag, others = _is_singular(pred), []
    for o in pool:
        if _related(o, concept) or not is_good_concept(o):
            continue
        of = find_concept_fragments(o, text, strict=True)
        if not of:
            continue
        mo = _concept_regex(o).search(of[0])
        op = of[0][mo.end():].strip()
        if (len(op.split()) >= 4 and _is_singular(op) == flag and op != pred
                and not _concept_regex(concept).search(op)):
            others.append(op)
    rng = random.Random(f"pred|{concept}")
    rng.shuffle(others)
    if len(others) < 3:
        return None
    options = [pred] + others[:3]
    rng.shuffle(options)
    return {"question": f"Which option correctly completes the sentence?  \u201c{stem} \u2026\u201d",
            "options": options, "correct_answer": pred}


def generate_mcq_set(concept: str, text: str, pool: list[str], n: int = 5, exclude=None) -> list[dict]:
    """Up to n DIFFERENT questions about one topic, all built from the student's notes:
      A) fill-in-the-blank of the topic, from each distinct sentence that mentions it
      B) sentence-completion: pick the correct continuation among other topics' continuations
      C) fill-in-the-blank of a RELATED topic inside the topic's sentences (tests connections)
    """
    frags = find_concept_fragments(concept, text, strict=False)
    questions, seen = [], set(exclude or [])   # exclude = questions this student already answered

    def add(q):
        if q and q["question"] not in seen:
            seen.add(q["question"])
            questions.append(q)

    for frag in frags[:3]:
        add(_cloze_question(frag, concept, pool))
    add(_predicate_question(concept, text, pool))
    for frag in frags[:4]:
        for other in pool:
            if not _related(other, concept) and is_good_concept(other) and _concept_regex(other).search(frag):
                add(_cloze_question(frag, other, pool))
    return questions[:n]


# ---------------------------------------------------------------------------
# Written tests: several different open questions for ONE topic
# ---------------------------------------------------------------------------
WHY_CUES = re.compile(r"\b(because|so that|used|helps?|allows?|enables?|makes?|faster|improves?|useful|important)\b", re.I)


def generate_written_set(concept: str, text: str, pool: list[str], n: int = 4, exclude=None) -> list[dict]:
    """Up to n different written questions about one topic, built from the student's notes.
    Each carries the note sentences it will be graded against (`references`):
      define   - "In your own words, what is X?"          graded against X's defining sentences
      compare  - "How is X different from Y?"              graded against both topics' sentences
      explain  - "Explain this statement from your notes"  graded against that statement
      why      - "Why is X useful or important?"           graded against a sentence giving a reason
    """
    seen = set(exclude or [])
    strict = find_concept_fragments(concept, text, strict=True)
    frags = find_concept_fragments(concept, text, strict=False)
    questions = []

    def add(q):
        if q["question"] not in seen and q["references"]:
            seen.add(q["question"])
            questions.append(q)

    define_refs = (strict or frags)[:3]
    add({"kind": "define", "question": f"In your own words, what is {concept}?", "references": define_refs})

    # compare: prefer a topic that appears in the same sentences as this one (e.g. "unlike X, Y ...")
    others = [o for o in pool if not _related(o, concept) and is_good_concept(o)
              and find_concept_fragments(o, text, strict=True)]
    together = [o for o in others if any(_concept_regex(o).search(f) for f in frags)]
    if others:
        other = (together or others)[0]
        mine = (strict or frags)[:1]
        theirs = find_concept_fragments(other, text, strict=True)[:1]
        add({"kind": "compare", "question": f"How is {concept} different from {other}? Explain both.",
             "references": mine + theirs + [" ".join(mine + theirs)]})

    for frag in frags:
        if frag not in define_refs[:1]:
            add({"kind": "explain", "question": f"Explain this statement from your notes in your own words: \u201c{frag}\u201d",
                 "references": [frag]})
            break

    why = next((f for f in frags if WHY_CUES.search(f)), None)
    if why:
        add({"kind": "why", "question": f"Why is {concept} useful or important? Use ideas from your notes.",
             "references": [why]})
    return questions[:n]
