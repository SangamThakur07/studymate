# Evaluation results

Notes used: `sample_notes.pdf` (2698 characters)

## 1. Retrieval quality
22 hand-written questions, 6 passages. A hit means a passage containing the answer sentence was ranked in the top k.
'Original' questions reuse words from the notes; 'paraphrase' questions deliberately share almost none, which is where semantic matching should help.

**Original questions** (14 questions)

| Method | Hit@1 | Hit@3 | MRR |
|---|---|---|---|
| embeddings | 79% | 93% | 0.88 |
| tfidf | 93% | 100% | 0.96 |
| hybrid | 93% | 100% | 0.96 |
| random baseline | 21% | 64% | - |

**Paraphrase stress set** (8 questions)

| Method | Hit@1 | Hit@3 | MRR |
|---|---|---|---|
| embeddings | 62% | 100% | 0.79 |
| tfidf | 38% | 62% | 0.56 |
| hybrid | 50% | 100% | 0.69 |
| random baseline | 23% | 69% | - |

## 2. Generated question quality
Topics found automatically: tokenization, stemming, lemmatization, word embeddings, attention mechanism, transformers, semantic similarity

Student takes one test per topic, in order. 'History-aware' = the agent remembers answered questions.

| Metric | No history | History-aware |
|---|---|---|
| Questions generated | 35 | 34 |
| Well-formed and unique | 33/35 = 94% | 34/34 = 100% |
| Correct answer visible in the question | 0 | 0 |
| Wrong option visible in the question | 0 | 0 |
| Repeated questions across tests | 2 | 0 |
| Topics with a full 5-question test | 7/7 | 6/7 |

When a topic has fewer than 5 fresh questions, the live app tops the test up with review questions on related topics.

## 3. Written-answer grading
Each answer is compared with the best of the top 3 sentences about the topic in the student's own notes. Score = what the app shows (0-10) after calibration, a minimum-substance rule (fewer than 4 meaningful words) and a key-term rule (must mention some of the notes' key terms); both rules cap the score below the pass mark. An answer counts as correct at 6 or more.

Similarity method used: **embeddings**

| Answer type | Answers | Mean similarity | Mean key-term coverage | Mean score (0-10) | Counted as correct (>= 6) |
|---|---|---|---|---|---|
| good | 7 | 0.95 | 0.63 | 10.00 | 7/7 |
| partial (very short) | 7 | 0.70 | 0.07 | 4.46 | 0/7 |
| vague but long | 4 | 0.75 | 0.00 | 5.00 | 0/4 |
| wrong | 7 | 0.35 | 0.09 | 0.07 | 0/7 |
| irrelevant | 7 | 0.03 | 0.00 | 0.00 | 0/7 |

Ideal: good answers counted as correct; every other type not counted as correct.

Misgraded answers: none

Caution: the scale and thresholds were set after seeing these examples, so the pass rates are optimistic. Add your own examples to eval_set.json (written by someone other than the author) to test it fairly.

## 4. Agent decision logic
| Test | Result |
|---|---|
| New student: starts at the foundation topic | PASS |
| Strong prerequisite: teaches the weak topic itself | PASS |
| Weak topic whose prerequisite is also weak: goes to the prerequisite | PASS |
| Everything mastered: advances | PASS |
| Mastery rises with correct answers and falls after a wrong one | PASS |

5/5 agent tests passed.
