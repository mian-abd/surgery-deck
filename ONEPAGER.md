# Argus

**A second layer of observation for the operating room.**

Argus watches the surgical field through an ordinary camera and flags preventable
safety events — a missed scrub-in, an instrument crossing the sterile boundary, a
final count that doesn't add up — **while the patient is still open**. Every alert
carries an evidence frame and is confirmed or dismissed by a human.

🔗 **Live demo:** https://orguard-frontend-598370539694.us-central1.run.app

---

**Problem — the last line of defense is a tired human counting under pressure.**
Each year in the U.S.: **~110,800 surgical-site infections (~$3.3B)**; retained
surgical items at roughly **1 in 10,000 procedures**, each costing
**$166k–$525k** and — as a "never event" — **not reimbursed**. Hand-hygiene
compliance sits at **40–70%**. Counts are manual, hygiene is unmonitored, and
today's OR camera systems mostly *record for later* rather than *warn in the moment*.

**Solution — four events, one closed loop.** Detection → evidence → human decision:

| | |
|---|---|
| **Instrument count** | persistent-ID tracking; initial vs. final mismatch |
| **Hand hygiene** | scrub-in verified at the sink before sterile entry |
| **Sterile-field breach** | instrument crossing sterile ↔ non-sterile |
| **Zone tracking** | operator-drawn sterile / tray / sink / non-sterile zones |

**How it works.** Camera → computer vision (**YOLO11** detection + **ByteTrack**
persistent IDs + **MediaPipe** hand landmarks) → a zone/state engine that reasons
about *transitions*, not single frames → **Gemini** turns each raw state change
into a clinician-readable explanation, independently re-examines the evidence
frame as a second opinion on whether the alert is real, and writes the
end-of-session safety report → a human confirms or dismisses. **Decision-support,
not diagnosis** — which keeps us out of the autonomous-medical-device regulatory
path. The deterministic rule engine stands alone: if Gemini is unreachable, every
alert still fires.

**Why now.** Ambient AI in the OR is funded and accelerating (**Apella $80M**,
**Caresyntax $302M**). Gemini makes real-time scene reasoning cheap enough to run
on hardware already in the room.

**Market (transparent math).** ~**57,000** U.S. ORs and procedure rooms (hospitals
+ ASCs) × ~**$20k/OR/year** = **$1.1B U.S. TAM**, inside an AI-in-OR market growing
**~$1B → $3.3B (~30% CAGR)**. Beachhead: **1,000–2,000 ORs → $20–40M ARR**.
*(Per-OR pricing is our assumption, not a cited figure.)*

**Wedge.** Incumbents **analyze after the fact, in the cloud** — OR Black Box
*records* for post-hoc review; Apella *optimizes* scheduling and documentation.
Argus **prevents in the moment**: a real-time closed loop, on **commodity cameras**
(not a six-figure sensor array), architected to run **on-prem so frames never leave
the hospital**, and general enough that a new safety event is a new rule, not a new
product. ROI is the whole sale — preventing **one** retained item pays for
**10–25 OR-years**.

**Traction.** Working prototype deployed on **Google Cloud Run**: live
camera → cloud → viewer streaming over WebSockets, real-time detection and
multi-object tracking with persistent IDs, operator-drawn zone reasoning, four
alert types each with a saved evidence frame, human review (confirm/dismiss), and
an auto-generated end-of-session report. **Gemini 3.5 Flash** narrates every alert
and independently re-checks the evidence frame — in testing it correctly flagged a
detection the image did not support, which is exactly the false-positive class
that makes safety alerts get ignored. Android viewer app via Capacitor.
Pre-revenue. *Next: fine-tune the instrument model on real surgical trays.*

**Team**

- **Igor Eduardo** — builds production AI for regulated healthcare (clinical AI, CV,
  edge, privacy). Author of two 2026 papers; hackathon winner. Leads DocMinds.ai.
- **Mian Abdullah** — CS & Philosophy, DePauw; research at Stanford. 4+ AI/ML and
  full-stack internships; 30+ projects.
- **Summer Pandey** — CS & Data Science, Augustana. Taught AI/ML at Stanford;
  award-winning Gemini hackathon projects.

**Ask.** A design-partner OR and a validation path on count accuracy and alert latency.

---

*Argus is a decision-support prototype. Every alert is a possible event requiring
human confirmation; it is not a medical device and makes no clinical claims.*
