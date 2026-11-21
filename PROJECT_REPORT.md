# StudyMate: An Autonomous Agentic NLP Learning Assistant with Hybrid Retrieval-Augmented Generation, Prerequisite Modeling, and Semantic Evaluation

**Format:** 7-Page Academic Standard Project Report  
**Authors / Team Members:**
1. **Sangam Thakur** (Registration No: 12403852)  
2. **Viren Poonia** (Registration No: 12409626)  
**Course Code:** CSE472 — Natural Language Processing (NLP)  
**GitHub Repository:** [https://github.com/SangamThakur07/studymate](https://github.com/SangamThakur07/studymate)  
**Academic Subject:** Natural Language Processing (NLP) / Artificial Intelligence  
**Date:** November 2026  

---

## Abstract

Traditional electronic learning systems and standard Retrieval-Augmented Generation (RAG) chatbots operate reactively: they answer user queries on demand but lack an internal model of what the learner knows, where their knowledge gaps lie, and what pedagogical interventions are required next. This report presents **StudyMate**, an autonomous, agentic learning assistant powered by classical and modern Natural Language Processing techniques. StudyMate combines an exponential moving average student mastery model with a NetworkX prerequisite Directed Acyclic Graph (DAG) to make goal-driven instructional decisions (*Intervene*, *Review*, or *Advance*).

Uploaded learning materials (PDFs) are segmented and indexed into a **Hybrid Retrieval** engine fusing 384-dimensional dense sentence embeddings (`all-MiniLM-L6-v2`) with sparse lexical vectors (`TfidfVectorizer`). The system autonomously formulates multiple-choice cloze questions—with distractors dynamically sampled from co-occurring concepts in the student's own notes—and structured written assessment prompts across four cognitive archetypes (*define*, *compare*, *explain*, *why*). Written responses are evaluated against retrieved note passages using calibrated cosine similarity constrained by a minimum substance rule, key-term coverage verification, and an anti-plagiarism copy-detection penalty. Empirical evaluation demonstrates that hybrid retrieval achieves **100% Hit@3** across both lexical and paraphrase query distributions, while the calibrated grading pipeline successfully separates substantive answers from verbose, vague responses.

**Keywords:** Natural Language Processing, Agentic AI, Hybrid RAG, Knowledge Graph, Semantic Textual Similarity, Educational Technology, Evaluation Benchmarks.

---

## 1. Introduction & Problem Formulation

### 1.1 Overview & Pedagogical Context
The emergence of transformer language models has revolutionized automated educational tools. While conversational search interfaces allow students to query textbook materials, real-world learning requires systematic progression through foundational prerequisites, continuous self-assessment, and diagnostic feedback.

### 1.2 Critical Limitations of Standard RAG Chatbots
Standard RAG systems exhibit three fundamental limitations when applied to education:
1. **Passive Architecture**: Standard chatbots require the learner to identify what questions to ask. A student with foundational misunderstandings cannot reliably self-diagnose their conceptual gaps.
2. **Absence of Mastery Modeling**: Ordinary RAG systems maintain no persistent representation of student retention or decay across topics over time.
3. **Vulnerability to Superficial Answers**: In automated answer grading, dense embedding similarity measures topical closeness rather than correctness. Consequently, vague responses (*"Tokenization is an important technique used in NLP applications"*) score artificially high (0.75+) against reference definitions.

### 1.3 Problem Statement
To design an autonomous, privacy-preserving NLP learning assistant capable of ingesting raw course notes (PDFs), modeling prerequisite concept hierarchies, synthesizing contextual assessment items without manual question banks, and objectively grading written answers without expensive external API subscriptions.

### 1.4 Core Objectives
- **Closed-Loop Agentic Control**: Develop an autonomous Perceive $\rightarrow$ Reason $\rightarrow$ Act $\rightarrow$ Audit loop that plans study sessions and records auditable reasoning traces into an `AgentActionLog` database.
- **Hybrid Information Retrieval**: Combine dense semantic vectors (`all-MiniLM-L6-v2`) with sparse lexical vectors (TF-IDF) to guarantee high passage retrieval under both verbatim and paraphrased querying.
- **Dynamic In-Corpus Question Generation**: Formulate multiple-choice cloze questions with distractors sampled from the same document, alongside 4 structured written question archetypes (*define*, *compare*, *explain*, *why*).
- **Calibrated Multi-Stage Answer Grading**: Implement length-gating heuristics, key-term coverage verification, and anti-plagiarism copy penalties to enforce rigorous grading.
- **Unified Production Architecture**: Deliver a responsive, single-server FastAPI/React application with salted PBKDF2 password hashing and JWT authentication.

---

## 2. Literature Review & Theoretical Foundations

### 2.1 Dense vs. Sparse Vector Representations
Information retrieval methods typically fall into two paradigms: sparse lexical frequency matching (TF-IDF, BM25) and dense semantic representations (transformers). Sparse representations excel when student queries share exact vocabulary with the source text but fail when queries use synonyms or paraphrases. Dense sentence embeddings map text into a continuous latent space where vector distance corresponds to semantic meaning:
$$\text{Cosine}(u, v) = \frac{u \cdot v}{\|u\| \|v\|}$$
While dense models capture semantic intent, they can occasionally return false positives on queries that share no technical terms. Fusing normalized dense cosine scores with sparse TF-IDF linear kernels combines lexical exactness with semantic generalization.

### 2.2 Knowledge Graphs & Prerequisite Dependency DAGs
Curriculum mastery is structured as a Directed Acyclic Graph (DAG) $G = (V, E)$, where vertices $V$ represent concepts and directed edges $E$ represent prerequisite requirements (*Tokenization $\rightarrow$ Word Embeddings $\rightarrow$ Attention $\rightarrow$ Transformers*). By applying topological sorting algorithms via NetworkX, the agent determines valid learning sequences and identifies root causes when a student struggles on downstream topics.

### 2.3 Automated Question Generation (AQG) & Distractor Selection
Cloze deletion constructs test items by masking conceptual target terms from source sentences. The primary challenge in automated MCQ generation lies in selecting plausible distractors. Random dictionary words create obvious, low-quality questions. StudyMate harvests candidate distractors directly from the co-extracted concept pool of the student's uploaded document, ensuring that incorrect choices are contextually plausible within the same domain.

### 2.4 Semantic Textual Similarity (STS) & Scoring Calibration
Evaluating free-form answers using unconstrained cosine similarity introduces severe grading inflation because dense embedding models reward topical keywords regardless of grammatical assertion. Objective grading requires multi-tiered constraints: brevity gating, key-term coverage verification, and verbatim lexical overlap capping.

---

## 3. System Design & Agentic Architecture

### 3.1 Ingestion & Document Processing Pipeline
When a student uploads lecture notes (PDF), StudyMate processes the document through an automated pipeline:
1. **Stream Parsing**: `pypdf` extracts raw character text streams, standardizing whitespace and line breaks.
2. **Sentence Segmentation**: Text is segmented using regex lookbehind patterns (`(?<=[.!?])\s+`).
3. **Sliding Window Chunking**: Text is organized into 600-character windows with a 1-sentence overlap, preserving semantic context across chunk boundaries.
4. **Dual Indexing**: Chunks are converted into 384-dimensional dense vectors (`all-MiniLM-L6-v2`) and sparse TF-IDF matrices, stored in SQLite.

### 3.2 Concept Extraction & Heuristic Filtering
KeyBERT (MiniLM) extracts candidate keyphrases with an n-gram range of (1, 2). To eliminate noisy fragments, StudyMate applies three rule-based filters:
- **Stop-Word Edge Filtering**: Discards phrases starting or ending with function words.
- **POS Tag Filtering**: Rejects pure verbs and generic prefixes like "various".
- **Grounding Support Rule**: Discards concepts lacking at least 2 complete supporting sentences in the document.

### 3.3 The Agentic Reasoning Loop (Perceive $\rightarrow$ Reason $\rightarrow$ Act $\rightarrow$ Audit)
The agent service executes an autonomous pedagogical decision cycle:
- **Perceive**: Computes current concept mastery using an Exponential Moving Average (EMA) over past test scores:
  $$\text{Mastery}_{\text{new}} = 0.7 \cdot \text{Mastery}_{\text{old}} + 0.3 \cdot \text{Score}_{\text{current}}$$
- **Reason**: Examines the prerequisite DAG. If a student demonstrates weak mastery (<60%) on an advanced concept whose prerequisite is also weak, the agent automatically intervenes and redirects learning to the foundation topic.
- **Act**: Dispatches appropriate pedagogical tools: topic briefing, 5-question MCQ generation, or written synthesis testing.
- **Audit**: Every decision and its rationale is permanently written to the `AgentActionLog` database table, providing examiners with a transparent audit trail.

---

## 4. Question Synthesis, Grading & Implementation

### 4.1 Hybrid RAG Retrieval Engine
Retrieval for explanations and grading references fuses dense and sparse similarities:
$$\text{Score}_{\text{hybrid}} = 0.5 \cdot \text{Norm}(\text{Cosine}(Q, C)) + 0.5 \cdot \text{Norm}(\text{TFIDF}(Q, C))$$
The top $k=3$ passages are retrieved and presented in the UI with transparency match scores.

### 4.2 Question Generation Archetypes
- **Cloze Multiple-Choice Questions**: Replaces the target concept with a blank (`_____`) in defining sentences. Distractors are drawn from related topics within the same notes. A session history buffer prevents question repeats across tests.
- **Written Synthesis Questions**: Formulates four cognitive questions per topic: (1) Define in own words, (2) Compare two related concepts, (3) Explain a specific statement from the notes, and (4) Explain why the concept is important in NLP systems.

### 4.3 Multi-Stage Answer Grading & Copy Detection
To ensure objective evaluation without human graders, written submissions pass through a 4-stage pipeline:
1. **Reference Matching**: Compares the submission against the top-3 defining sentences in the notes using MiniLM cosine similarity.
2. **Substance Threshold Gate**: Answers with fewer than 4 non-stopword tokens are capped at 4.5/10.
3. **Key-Term Coverage Check**: Requires the presence of the reference sentence's key technical lemmas. Generic or vague answers without core terms are capped at 5.0/10.
4. **Anti-Copy Plagiarism Penalty**: Submissions with >90% lexical overlap with the source notes are penalized below passing (<5.0/10) with the feedback: *"Put it in your own words."*

### 4.4 Technical Implementation & Security
The system utilizes FastAPI (Python 3.10), SQLite, PyTorch, SentenceTransformers, and React 18 with Vite. Security features include salted PBKDF2-HMAC-SHA256 password hashing (200,000 iterations), cryptographically signed JWT sessions (7-day validity), and multi-tenant student data isolation. The compiled React frontend (`frontend/dist`) is served directly by FastAPI from port 8000 in a unified single-server deployment.

---

## 5. Empirical Evaluation & Benchmark Results

### 5.1 Evaluation Setup & Benchmark Corpus
The evaluation harness (`backend/eval/run_eval.py`) was benchmarked against `sample_notes.pdf` (2,698 characters, covering Tokenization, Stemming, Lemmatization, Word Embeddings, Attention Mechanism, Transformers, Semantic Similarity).

### 5.2 Retrieval Quality Benchmark (Hit@k & MRR)
Evaluated on 22 hand-crafted queries (14 verbatim phrasing, 8 paraphrase stress queries) over 6 indexed document chunks:

| Retrieval Method | Orig Hit@1 | Orig Hit@3 | Orig MRR | Para Hit@1 | Para Hit@3 | Para MRR |
|---|---|---|---|---|---|---|
| **Dense Embeddings (MiniLM)** | 79% | 93% | 0.88 | **62%** | **100%** | **0.79** |
| **Sparse TF-IDF** | **93%** | **100%** | **0.96** | 38% | 62% | 0.56 |
| **Hybrid (StudyMate)** | **93%** | **100%** | **0.96** | 50% | **100%** | 0.69 |
| Random Baseline | 21% | 64% | — | 23% | 69% | — |

*Analysis:* While TF-IDF achieves superior Hit@1 on verbatim queries (93%), it degrades substantially under semantic paraphrasing (38% Hit@1). Hybrid retrieval achieves **100% Hit@3 across both test regimes**.

### 5.3 Question Generation Quality Benchmark

| Metric | Stateless Generator | History-Aware (StudyMate) |
|---|---|---|
| Total Questions Generated | 35 | 34 |
| Well-Formed & Syntactically Unique | 94% (33/35) | **100% (34/34)** |
| Correct Answer Leaked in Prompt | 0% (0/35) | **0% (0/34)** |
| Repeated Questions Across Sessions | 2 | **0** |
| Topics with Complete 5-Question Test | 7/7 | 6/7 (topped up with review) |

### 5.4 Written Answer Grading Calibration

| Answer Category | Sample Size | Mean Similarity | Key-Term Coverage | Mean Score | Pass Rate ($\ge 6.0$) |
|---|---|---|---|---|---|
| **Substantive Correct Answers** | 7 | 0.95 | 0.63 | **10.00** | **7 / 7 (100%)** |
| **Partial / Very Brief Answers** | 7 | 0.70 | 0.07 | 4.46 | **0 / 7 (0%)** |
| **Vague but Verbose Answers** | 4 | 0.75 | 0.00 | 5.00 | **0 / 4 (0%)** |
| **Wrong Topic Answers** | 7 | 0.35 | 0.09 | 0.07 | **0 / 7 (0%)** |
| **Irrelevant / Off-Topic Answers** | 7 | 0.03 | 0.00 | 0.00 | **0 / 7 (0%)** |

*Analysis:* Before calibration, vague verbose answers scored 7.55/10 (falsely passing). The key-term coverage rule correctly capped 100% of these responses to 5.0/10, completely eliminating false passes on the benchmark set. All 5 formal agent state transition tests passed (**100% pass rate**).

---

## 6. Discussion, Conclusion & References

### 6.1 Limitations & Error Analysis
1. **Topical vs. Factual Similarity**: Dense embeddings reward domain relatedness rather than factual assertion. A verbose answer scored 0.75 raw cosine similarity, highlighting that vector similarity must be constrained by key-term verification rules in automated grading.
2. **Heuristic Topic Filtering**: Concept extraction relies on defined sentence syntax (*"X is a..."*); unstructured slides with dense formulas or code yield fewer concepts.
3. **Prerequisite Graph Linearity**: In offline mode without an external LLM, prerequisite DAGs follow linear document order. Non-linear dependencies require manual ontology seeding or LLM graph synthesis.

### 6.2 Future Work
- **Local LLM Integration**: Connecting quantised open-weight models (Llama 3.2 3B via Ollama) for multi-turn conversational viva examinations.
- **Multimodal OCR Ingestion**: Incorporating vision transformers (TrOCR) to parse physical handwritten notes and mathematical formulas.
- **Spaced Repetition Scheduling**: Implementing the SuperMemo SM-2 algorithm to schedule retention reviews dynamically.

### 6.3 Concluding Remarks
StudyMate demonstrates that an effective educational AI tool must transcend reactive conversational search. By combining persistent student mastery modeling, prerequisite graph reasoning, hybrid vector retrieval, and multi-criteria answer validation, the platform transforms static lecture notes into an interactive, rigorous, and personalized learning environment.

### 6.4 Academic References
- Reimers, N., & Gurevych, I. (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks*. EMNLP 2019.
- Grootendorst, M. (2020). *KeyBERT: Minimal keyword extraction with BERT*. Zenodo.
- Robertson, S., & Zaragoza, H. (2009). *The Probabilistic Relevance Framework: BM25 and Beyond*. Foundations and Trends in Information Retrieval, 3(4), 333-389.
- Vaswani, A., et al. (2017). *Attention Is All You Need*. NeurIPS 2017.
- Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS 2020.

**Project Source Code:** [https://github.com/SangamThakur07/studymate](https://github.com/SangamThakur07/studymate)
