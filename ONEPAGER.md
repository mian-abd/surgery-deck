# Argus

**A second pair of eyes for the operating room.** Argus watches the surgical field
through an ordinary camera and flags preventable safety events — a missed scrub-in,
an instrument crossing the sterile boundary, a count that doesn't reconcile —
**while the patient is still open**.

🔗 **Demo:** https://orguard-frontend-598370539694.us-central1.run.app  ·  💻 **Code:** https://github.com/mian-abd/surgery-deck

**Problem.** Per year in the U.S.: **~110,800 surgical-site infections (~$3.3B)**, and
retained surgical items at roughly **1 in 10,000 procedures** — each costing
**$166k–$525k** and, as a "never event," **not reimbursed**. Hand-hygiene compliance
sits at **40–70%**. The last line of defense is a tired human counting under pressure.

**Insight — detection isn't the hard part; false positives are.** Geometric rules
misfire on occlusion and bad camera angles, staff learn to dismiss them, and a safety
system that gets ignored is worse than none — it manufactures the appearance of
coverage. So Argus runs **two layers**: a deterministic rule engine, plus **Gemini
re-examining the evidence frame** to judge whether the image actually supports the
alert. In testing, Gemini **overruled the detector**. That disagreement is the product.

**What it does.** Four closed-loop events — instrument count (initial vs. final), hand
hygiene, sterile-field breach, zone tracking — each with a saved evidence frame, human
confirm/dismiss, and an auto-generated safety report.

**How.** YOLO11 + ByteTrack persistent IDs + MediaPipe hands → a state engine reasoning
over *transitions*, not frames → **Gemini** narrates each event, audits the frame, and
writes the report → a human confirms. **Decision-support, not diagnosis.** If Gemini is
unreachable, every alert still fires.

**Market.** ~**57,000** U.S. ORs and procedure rooms × ~**$20k/OR/yr** = **$1.1B TAM**,
inside an AI-in-OR market growing **~$1B → $3.3B (~30% CAGR)**. Beachhead 1,000–2,000
ORs → **$20–40M ARR**. One prevented retained item pays for **10–25 OR-years**.
*(Per-OR price is our assumption, not a cited figure.)*

**Wedge.** Apella ($80M) optimizes scheduling; OR Black Box records for post-hoc review.
Argus **prevents in the moment**, on commodity cameras, architected to run **on-prem so
frames never leave the hospital**.

**Traction.** Live on Google Cloud Run — open the link and run a session. Real-time
detection and tracking, operator-drawn zones, four alert classes with evidence, review,
and report. **Gemini 3.5 Flash narrates and audits every alert in production.** Android
viewer via Capacitor. Pre-revenue. *Next: fine-tune the instrument model on real trays.*

**Team.** **Igor Eduardo** — production AI for regulated healthcare (clinical AI, CV,
edge); two 2026 papers; leads DocMinds.ai. **Mian Abdullah** — CS & Philosophy, DePauw;
research at Stanford; 4+ AI/ML internships. **Summer Pandey** — CS & Data Science,
Augustana; taught AI/ML at Stanford; award-winning Gemini projects.

**Ask.** A design-partner OR and a validation path on count accuracy and alert latency.

*Decision-support prototype. Every alert is a possible event requiring human
confirmation; not a medical device.*
