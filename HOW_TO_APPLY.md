# Update 17: written tests with several questions, and copy detection

Builds on update 16. No new packages, no database change. Copy these 7 files over your studymate folder:

backend/app/schemas.py
backend/app/routers/agent.py
backend/app/services/agent_service.py
backend/app/tools/mcq_tools.py
backend/app/tools/evaluation_tools.py
backend/eval/run_eval.py
frontend/src/pages/Dashboard.jsx

Then close the app and double-click start_shared.bat again.

## What changed
Choosing "Written test" now gives up to 4 different questions about the topic, all from your notes:
  - define    "In your own words, what is X?"
  - compare   "How is X different from Y? Explain both."
  - explain   "Explain this statement from your notes in your own words"
  - why       "Why is X useful or important?"
Each is graded against the note sentences it came from. If a topic's own questions are used up, the test is
topped up with review questions on related topics (labelled), exactly like the multiple-choice test.

Pasting the notes' sentence no longer earns marks: an answer that is almost word for word the same as the
notes is capped below the pass mark with "Put it in your own words."

## Limit worth knowing
The "explain" and "compare" questions are graded by similarity and key terms, not by understanding. A
student who rewords the notes' sentence only slightly can still score well. Real feedback on reasoning needs a
language model.
