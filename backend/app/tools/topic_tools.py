"""
Topic extraction = two sources, then one shared clean-up.

  1. DEFINED TERMS (rule-based): the subject of sentences like "Tokenization is...",
     "Lemmatization reduces...", "An attention mechanism allows...". Study notes define
     their topics this way, so this finds them reliably even when a keyword model does not.
     PDF run-together headings ("Tokenization Tokenization is") are handled by spotting
     the repeated heading before the verb.
  2. KEYPHRASES (statistical): KeyBERT (embedding based, with MMR for diversity) or TF-IDF.

clean_concepts() then filters generic words/verb phrases/title lines, merges overlaps,
and keeps topics the notes actually define.
"""
import re

from app.tools.knowledge_tools import extract_keywords
from app.tools.mcq_tools import _sentences, clean_concepts, is_good_concept

DEF_VERBS = {"is", "are", "refers", "means", "reduces", "represent", "represents", "measures",
             "allows", "computes", "splits", "converts", "maps", "describes", "defines"}
DETERMINERS = {"a", "an", "the"}
PRONOUNS = {"it", "this", "that", "these", "those", "they", "which", "there", "he", "she", "we", "you"}
BAD_INNER = {"and", "or", "of", "to", "in", "for", "with", "by", "on", "as", "than", "but"}


def extract_defined_terms(text: str) -> list[str]:
    terms, seen = [], set()
    for sent in _sentences(text):
        toks = sent.split()
        vi = next((i for i, t in enumerate(toks[:12]) if i >= 1 and t.lower().strip(",;:") in DEF_VERBS), None)
        if vi is None:
            continue
        pre = [t for t in toks[:vi] if t.lower() not in DETERMINERS]
        subject = None
        for L in (3, 2, 1):                       # heading echoed by the body: "X X is ..."
            if len(pre) >= 2 * L and [w.lower() for w in pre[-L:]] == [w.lower() for w in pre[-2 * L:-L]]:
                subject = pre[-L:]
                break
        if subject is None and 1 <= len(pre) <= 3:
            subject = pre
        if not subject:
            continue
        words = [re.sub(r"[^A-Za-z0-9\-]", "", w).lower() for w in subject]
        if (not all(words) or words[0] in PRONOUNS or any(w in BAD_INNER for w in words)):
            continue
        term = " ".join(words)
        if term not in seen and is_good_concept(term):
            seen.add(term)
            terms.append(term)
    return terms


ENOUGH_DEFINED_TOPICS = 6


def extract_topics(text: str, limit: int = 12) -> list[str]:
    """The topics shown to the student. Defined terms are cheap (rules only), so try them first;
    the slower keyphrase model is used only when the notes define too few topics."""
    defined = extract_defined_terms(text)
    topics = clean_concepts(defined, text, limit=limit)
    if len(topics) >= ENOUGH_DEFINED_TOPICS:
        return topics
    return clean_concepts(defined + extract_keywords(text, top_n=40), text, limit=limit)
