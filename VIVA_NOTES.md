# StudyMate — Viva & Presentation Defense Guide

## 🎙️ 30-Second Elevator Pitch
> "StudyMate is an agentic, NLP-driven study assistant. Unlike typical chatbots that just answer questions, StudyMate models what a student knows using an exponential moving average mastery score and a prerequisite knowledge graph. It autonomously decides whether to introduce new concepts or intervene on weak foundations. All learning materials are dynamically indexed using Hybrid RAG combining dense MiniLM embeddings and lexical TF-IDF. Test questions and evaluation are grounded directly in the student's own uploaded notes with automated copy-paste detection."

---

## 💡 Top 10 Likely Questions & Winning Answers

### 1. What makes this "Agentic" rather than just a standard RAG pipeline?
**Answer**:
A standard RAG pipeline is reactive: user asks a question $\rightarrow$ system retrieves chunks $\rightarrow$ returns an answer.
StudyMate is autonomous and goal-driven:
1. **Perceive**: Reads student mastery state across concepts.
2. **Decide**: Consults a NetworkX DAG of prerequisites to determine the optimal learning path.
3. **Act**: Generates quizzes, tests understanding, and actively updates the mastery model.
4. **Audit**: Every action is saved to `AgentActionLog` with transparent reasoning.

### 2. Why use Hybrid Retrieval instead of pure vector embeddings?
**Answer**:
Our empirical evaluation showed that on exact-match or keyword-heavy queries, TF-IDF achieved **93% Hit@1** and **100% Hit@3**, whereas dense embeddings scored 79% Hit@1. However, under heavy paraphrase (where the student uses different vocabulary), TF-IDF dropped sharply to **38% Hit@1**, while embeddings maintained **62% Hit@1** and **100% Hit@3**. Hybrid fusion captures the lexical precision of BM25/TF-IDF while retaining semantic generalization on paraphrases.

### 3. How do you evaluate written student answers without an LLM?
**Answer**:
We evaluate written answers by calculating cosine similarity between the student's response embedding and the top-3 reference definition sentences extracted from their notes. To prevent "vague but verbose" answers from gaming the cosine metric, we enforce:
- A minimum substance rule (must contain $\ge 4$ non-stopword tokens).
- A key-term coverage requirement matching core terminology from the source text.
- Anti-plagiarism copy detection: answers verbatim identical to the source text are penalized to encourage students to explain concepts in their own words.

### 4. How does the question generation work?
**Answer**:
We use rule-grounded cloze deletion (fill-in-the-blank) and template patterns (*define*, *compare*, *explain*, *why*). Distractors (wrong options) are sampled from the same document’s extracted concept pool rather than generic dictionaries, ensuring high contextual plausibility.

### 5. What are the known limitations of this approach?
**Answer**:
1. Complex multi-sentence conceptual reasoning grading still benefits from an LLM.
2. Concept extraction relies on defined sentence structures and KeyBERT noun phrases; non-standard PDF formats may yield fewer topics.
3. Prerequisite DAG extraction currently relies on document order and topological sorting unless augmented by an external curriculum ontology.

---

## 🎬 3-Minute Live Demo Flow
1. **Sign In**: Open the single-server app on `http://localhost:8000` (or the deployed public link) and log in.
2. **Upload Notes**: Upload `sample_notes.pdf`. Show the extracted topics (*tokenization*, *word embeddings*, *attention mechanism*, etc.).
3. **Agent Decision**: Point to the "Agent Reasoning" card explaining why it selected the foundation concept first.
4. **Retrieved Passages**: Show the "Retrieved from your notes" card displaying hybrid search scores.
5. **Take Test**:
   - Answer an MCQ question correctly $\rightarrow$ show mastery bar increasing.
   - For written question, show what happens if you type a vague answer vs a detailed answer in your own words.
