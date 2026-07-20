# Argus

**A second pair of eyes for the operating room.**

Argus watches the surgical field through an ordinary camera and flags preventable
safety events — a missed scrub-in, an instrument crossing the sterile boundary, a
final count that doesn't reconcile — **while the patient is still open**. Every
alert carries an evidence frame and is confirmed or dismissed by a human.

🔗 **Live demo:** https://orguard-frontend-598370539694.us-central1.run.app
💻 **Code:** https://github.com/mian-abd/surgery-deck

---

**Problem — the last line of defense is a tired human counting under pressure.**
Each year in the U.S.: **~110,800 surgical-site infections (~$3.3B)**; retained
surgical items at roughly **1 in 10,000 procedures**, each costing
**$166k–$525k** and — as a "never event" — **not reimbursed**. Hand-hygiene
compliance sits at **40–70%**. Counts are manual, hygiene is unmonitored, and
today's OR camera systems mostly *record for later* rather than *warn in the moment*.

**The insight — detection isn't the hard part. False positives are.**
Geometric rules fire on occlusion, a bad camera angle, a hand passing through
frame. Staff learn to dismiss them, and a safety system that gets ignored is
worse than none: it manufactures the appearance of coverage. So Argus is **two
layers** — a deterministic rule engine that catches the event, and **Gemini
re-examining the actual evidence frame** to judge whether the image supports the
alert. In our own testing Gemini **overruled the detector**, correctly reporting
that a flagged frame didn't show what the rule claimed. That disagreement is the
product: alerts that survive a second opinion are worth a human's attention.

**Solution — four events, one closed loop.**

| | |
|---|---|
| **Instrument count** | persistent-ID tracking; initial vs. final mismatch |
| **Hand hygiene** | scrub-in verified at the sink before sterile entry |
| **Sterile-field breach** | instrument crossing sterile ↔ non-sterile |
| **Zone tracking** | operator-drawn sterile / tray / sink / non-sterile zones |

**How it works.** Camera → computer vision (**YOLO11** + **ByteTrack** persistent
IDs + **MediaPipe** hands) → a state engine reasoning over *transitions*, not
single frames → **Gemini** narrates the event, audits the evidence frame, and
writes the end-of-session report → a human confirms. **Decision-support, not
diagnosis**, which keeps us off the autonomous-medical-device path. The rule
engine stands alone: if Gemini is unreachable, every alert still fires.

**Why now.** Ambient AI in the OR is funded and accelerating (**Apella $80M**,
**Caresyntax $302M**). Gemini makes real-time scene reasoning cheap enough to run
on hardware already in the room.

**Market (transparent math).** ~**57,000** U.S. ORs and procedure rooms × ~**$20k/OR/yr**
= **$1.1B U.S. TAM**, inside an AI-in-OR market growing **~$1B → $3.3B (~30% CAGR)**.
Beachhead: **1,000–2,000 ORs → $20–40M ARR**. *(Per-OR price is our assumption,
not a cited figure.)* ROI carries the sale: preventing **one** retained item pays
for **10–25 OR-years**.

**Wedge.** Incumbents **analyze after the fact** — OR Black Box *records* for
post-hoc review; Apella *optimizes* scheduling. Argus **prevents in the moment**,
on **commodity cameras**, architected to run **on-prem so frames never leave the
hospital**, and general enough that a new safety event is a new rule — not a new
product.

**Traction.** Live on Google Cloud Run — open the link and run a session.
Real-time detection and tracking, operator-drawn zone reasoning, four alert
classes each with a saved evidence frame, human review, and an auto-generated
report. **Gemini 3.5 Flash narrates and audits every alert in production.**
Android viewer app via Capacitor. Pre-revenue. *Next: fine-tune the instrument
model on real surgical trays.*

**Team**

- **Igor Eduardo** — production AI for regulated healthcare (clinical AI, CV, edge,
  privacy). Two 2026 papers; hackathon winner. Leads DocMinds.ai.
- **Mian Abdullah** — CS & Philosophy, DePauw; research at Stanford. 4+ AI/ML and
  full-stack internships; 30+ projects.
- **Summer Pandey** — CS & Data Science, Augustana. Taught AI/ML at Stanford;
  award-winning Gemini hackathon projects.

**Ask.** A design-partner OR and a validation path on count accuracy and alert latency.

---

*Argus is a decision-support prototype. Every alert is a possible event requiring
human confirmation; it is not a medical device and makes no clinical claims.*
