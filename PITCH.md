# Argus — Investor Pitch

**AI that watches the operating room so nothing gets left behind.**

Argus is a computer-vision safety monitor for the OR. Off a simple camera feed,
it tracks every instrument, checks hand hygiene, watches the sterile field, and
raises reviewable alerts in real time — turning "never events" that cost lives
and billions into events that get caught *before* the patient is closed.

> One-liner: **"A flight-data recorder + co-pilot for surgery."**

---

## 1. The Problem — preventable harm, at scale, still happening every day

Surgery is safer than ever, yet the same avoidable mistakes keep happening
because the last line of defense is a tired human doing a manual count.

- **~4,000 surgical "never events" per year in the U.S.** — a Johns Hopkins
  analysis found a surgeon leaves a foreign object in a patient **~39 times a
  week**, performs the wrong procedure **~20 times a week**, and operates on the
  wrong site **~20 times a week**. Outcomes: **death in 6.6%, permanent injury in
  33%.** ([Johns Hopkins / *Surgery*, 2012](https://www.sciencedaily.com/releases/2012/12/121219111336.htm))
- **$1.3B in malpractice payouts** for never events over 20 years; roughly
  **$1B/year** cost to the health system. ([AboutLawsuits summary of the JHU study](https://www.aboutlawsuits.com/malpractice-payments-surgical-never-events-study-38968/))
- **Retained surgical items (RSI):** ~**4,500–6,000 cases/year**, ~1 in 10,000
  procedures. Each event costs **~$166,000 and up to ~$525,000** all-in (removal,
  legal, indemnity) — and it's a "never event," so **insurers don't reimburse**
  the hospital. ([RSI facts & figures](https://www.davidrickslaw.com/blog/retained-surgical-item-facts-figures-and-statistics.cfm), [AORN: cost of RSIs](https://www.aorn.org/outpatient-surgery/article/the-high-cost-of-retained-surgical-items))
- **Surgical site infections (SSIs):** **~160,000–300,000/year**, the most common
  and costly hospital infection, adding **~$20,000+ per case** and **$3.5–10B/year**
  in the U.S. Hand hygiene is a primary driver — a **10% improvement in hand
  hygiene → ~6% fewer** healthcare-associated infections. ([SSI burden](https://www.sciencedaily.com/releases/2017/01/170119161551.htm), [hand-hygiene & HAI reduction, CDC/EID](https://wwwnc.cdc.gov/eid/article/22/9/15-1440_article))
- **Hand-hygiene compliance is chronically low** — commonly **40–70%**, and as low
  as **12–34%** in some settings. Nobody is watching consistently. ([hand-hygiene compliance review](https://pmc.ncbi.nlm.nih.gov/articles/PMC4994356/))

**Why it persists:** counts are manual, hygiene is unmonitored, and today's OR
"black box" systems mostly *record for later* — they don't *warn in the moment*.

---

## 2. Why Now

- **Surgical volume is enormous and growing:** **40–50M major surgeries/year in
  the U.S.** and **~310M globally.** ([U.S. & global surgery volumes](https://pmc.ncbi.nlm.nih.gov/articles/PMC7388795/))
- **Computer vision is finally good enough** to track small instruments, hands,
  and zones in real time on commodity hardware.
- **Reimbursement pressure:** never events are non-reimbursable and increasingly
  penalized — hospitals now have a hard-dollar reason to prevent them.
- **The category is being funded right now** (see Competition) — capital and
  hospital buyers are actively moving into AI in the OR.

---

## 3. The Solution — Argus

A camera-light platform that runs on the OR feed and does four things **live**:

1. **Instrument count** — detects and tracks every tool with persistent IDs;
   compares an initial vs. final count and flags any mismatch (the RSI killer).
2. **Hand-hygiene check** — verifies scrub-in at the sink before sterile entry;
   flags noncompliance.
3. **Sterile-field breach** — watches for instruments/hands crossing sterile ↔
   non-sterile boundaries and flags possible contamination.
4. **Live dashboard, human review & report** — every alert is a *possible* event
   with a saved evidence frame, confirmed or dismissed by a human, and rolled
   into an end-of-session safety report.

**Design principles that make it sellable:** camera-light (runs off existing/cheap
cameras — no six-figure sensor array), cloud-native (Google Cloud), multi-camera
ready, and **decision-support, not autonomy** — Argus flags "possible" events for
human confirmation, sidestepping the regulatory burden of an autonomous medical
device while still delivering the value.

> **Live demo:** working prototype deployed on Google Cloud Run — dashboard,
> real-time detection, alerts, review, and report all functional today.

---

## 4. Market Size

**The value pool (cost of the problem we remove): ~$5–11B/year in the U.S. alone**
— SSIs ($3.5–10B) + never events (~$1B) + retained-item removal costs. Globally,
multiples of that.

**Software market (SAM proxy):** AI & analytics in surgery is **$255M (2024) →
$951M (2030) at ~24.5% CAGR**, with **computer vision the single largest segment
(~38%)**. The broader AI-surgery stack (incl. robotics) is **$7.5B → $25B by
2030**. ([AI & analytics in surgery market](https://www.globenewswire.com/news-release/2025/03/06/3038361/28124/en/Artificial-Intelligence-and-Analytics-in-Surgery-Research-Report-2024-2030-Global-Push-for-Digital-Transformation-in-Healthcare-Drives-Growth.html), [AI-based surgical robots market](https://www.grandviewresearch.com/industry-analysis/artificial-intelligence-based-surgical-robots-market))

**Bottom-up (illustrative — assumptions, not cited fact):**
- ~**50,000+ operating & procedure rooms** in the U.S. (hospitals + ASCs).
- Per-OR SaaS at **~$12k/OR/year** → **~$600M U.S. SAM**; global scales several ×.
- **SOM (3–5 yrs):** 1,000–2,000 ORs → **$12–30M ARR** — a credible early beachhead.

| Layer | Framing | Figure |
|---|---|---|
| **TAM** | Global AI-in-surgery software + the harm-cost pool it addresses | **$950M (2030 SW) / $5–11B/yr U.S. harm** |
| **SAM** | U.S. ORs × per-OR SaaS | **~$600M/yr** |
| **SOM** | 1–2k ORs in 3–5 yrs | **$12–30M ARR** |

---

## 5. Business Model & Unit Economics

- **SaaS, per-OR subscription** (~$10–15k/OR/year), camera-light install → high
  gross margin, low deployment cost.
- **Land-and-expand:** start with the safety module (count/hygiene/breach), expand
  into OR analytics, EHR documentation, and multi-camera coverage.
- **ROI is the whole sale:** preventing **one** retained item (~$166k–$525k) pays
  for **10–50 OR-years** of Argus. A single avoided never-event settlement funds a
  hospital-wide rollout. This is a rare "safety product that also saves money."
- **Buyers:** hospital risk/quality officers, perioperative directors, malpractice
  insurers (who have direct financial incentive to fund adoption).

---

## 6. Competition & Our Wedge

The category is real and being funded — validation, not a red flag:

- **Apella** (founded 2020) — raised **$80M Series B (Jan 2026)** + $21M Series A;
  ambient AI/CV, 500k cases, Houston Methodist 200+ ORs. **Focus: OR *efficiency /
  scheduling / EHR documentation*.** ([Apella $80M raise](https://www.fiercehealthcare.com/health-tech/or-optimization-platform-apella-raises-80m-fuel-health-system-expansion))
- **OR Black Box / SST** (founded 2014) — 360° audio/video **recorder** for
  *post-hoc* review. ([OR camera landscape](https://apella.io/blog/exploring-the-or-status-camera-landscape-stryker-karl-storz-sst-or-black-box-artisight-proximie-and-apella))
- Also in the room: Stryker, Karl Storz, Artisight, Proximie.

**Argus's wedge:** everyone else **optimizes or records**. Argus is **real-time
patient-safety prevention** — it warns *in the moment*, on **commodity cameras**
(not a six-figure sensor array), with reviewable evidence and an audit-ready
report. We attack the specific, non-reimbursable, litigated harms (RSI, hygiene,
contamination) that map directly to hard-dollar hospital losses.

---

## 7. Traction & Roadmap

- **Now:** functional prototype live on Google Cloud — real-time detection +
  tracking, hand/zone reasoning, alerts, human review, end-of-session report;
  Android viewer app; one-click live demo.
- **Next 6–12 mo:** design-partner hospital/ASC pilots; fine-tune the instrument
  model on real trays; validation study on count-accuracy and alert latency;
  SOC-2 / HIPAA posture.
- **12–24 mo:** multi-camera OR coverage, EHR write-back, insurer partnerships,
  regulatory strategy (decision-support pathway).

---

## 8. The Ask

Raising a **[pre-seed/seed — $ amount]** round to:
1. Land **3–5 design-partner ORs** and run a count-accuracy/latency validation.
2. Harden the model + platform (real surgical-instrument training data).
3. Stand up compliance (HIPAA/SOC-2) and the first insurer conversation.

**Use of funds:** ~[X] engineering, ~[Y] clinical/regulatory, ~[Z] pilot GTM.
**Milestone to next round:** signed pilots + validated safety metrics → Series A.

---

## Appendix A — 5-Minute Pitch Script (timed)

- **0:00–0:30 — Hook.** "Right now, somewhere in the U.S., a surgeon is closing a
  patient with a sponge still inside. It happens ~39 times a week. Argus makes
  sure it doesn't."
- **0:30–1:30 — Problem.** ~4,000 never events/yr, 6.6% fatal; RSIs cost up to
  $525k each and aren't reimbursed; SSIs cost $3.5–10B/yr; hand hygiene sits at
  40–70%. The last defense is a manual count.
- **1:30–2:30 — Solution + demo.** Show the live dashboard: instruments tracked,
  count captured, a hygiene miss, a sterile breach, a count mismatch — each with
  an evidence frame and a report. "Camera-light, real-time, human-in-the-loop."
- **2:30–3:30 — Market.** $5–11B/yr U.S. harm pool; AI-in-surgery software $950M
  by 2030 at 24.5% CAGR; ~$600M U.S. SAM bottom-up. Volume: 40–50M U.S. surgeries.
- **3:30–4:15 — Business + moat.** Per-OR SaaS; one prevented RSI pays 10–50
  OR-years. Competitors optimize or record; **we prevent, in real time, on cheap
  cameras.**
- **4:15–5:00 — Traction + ask.** Live prototype on GCP today; raising $[X] for
  design-partner pilots + a validation study to hit Series A.

## Appendix B — Key Numbers (cheat sheet)

| Metric | Figure | Source |
|---|---|---|
| U.S. surgical never events / yr | ~4,000 (death 6.6%, perm. injury 33%) | Johns Hopkins / *Surgery* 2012 |
| Never-event malpractice payouts | $1.3B / 20 yrs (~$1B/yr) | JHU / NPDB |
| Retained surgical items / yr | ~4,500–6,000 (~1 in 10,000 ops) | RSI literature |
| Cost per retained item | ~$166k, up to ~$525k (non-reimbursed) | PA Patient Safety Authority / AORN |
| SSIs / yr | ~160,000–300,000; $3.5–10B/yr; +$20k/case | CDC / SSI studies |
| Hand-hygiene compliance | ~40–70% (as low as 12–34%) | Hand-hygiene reviews |
| U.S. / global surgeries per yr | 40–50M / ~310M | Surgery-volume studies |
| AI-in-surgery software market | $255M (2024) → $951M (2030), 24.5% CAGR | Market research (GlobeNewswire) |
| Computer-vision share of that market | ~38% (largest segment) | Market research |
| Comparable funding (Apella) | $80M Series B, Jan 2026 | Fierce Healthcare |

## Sources

- Johns Hopkins / *Surgery* never-events study — https://www.sciencedaily.com/releases/2012/12/121219111336.htm
- Never-event malpractice payouts — https://www.aboutlawsuits.com/malpractice-payments-surgical-never-events-study-38968/
- Retained surgical item facts & figures — https://www.davidrickslaw.com/blog/retained-surgical-item-facts-figures-and-statistics.cfm
- AORN — the high cost of retained surgical items — https://www.aorn.org/outpatient-surgery/article/the-high-cost-of-retained-surgical-items
- RSI incidence 2016–2023 (medRxiv) — https://www.medrxiv.org/content/10.1101/2025.06.26.25329866v1.full
- SSIs most common & costly hospital infection — https://www.sciencedaily.com/releases/2017/01/170119161551.htm
- Hand hygiene & HAI reduction (CDC/EID) — https://wwwnc.cdc.gov/eid/article/22/9/15-1440_article
- Hand-hygiene compliance review (PMC) — https://pmc.ncbi.nlm.nih.gov/articles/PMC4994356/
- U.S. & global surgery volumes (PMC) — https://pmc.ncbi.nlm.nih.gov/articles/PMC7388795/
- AI & analytics in surgery market (2024–2030) — https://www.globenewswire.com/news-release/2025/03/06/3038361/28124/en/Artificial-Intelligence-and-Analytics-in-Surgery-Research-Report-2024-2030-Global-Push-for-Digital-Transformation-in-Healthcare-Drives-Growth.html
- AI-based surgical robots market — https://www.grandviewresearch.com/industry-analysis/artificial-intelligence-based-surgical-robots-market
- Apella $80M Series B — https://www.fiercehealthcare.com/health-tech/or-optimization-platform-apella-raises-80m-fuel-health-system-expansion
- OR camera landscape (Apella blog) — https://apella.io/blog/exploring-the-or-status-camera-landscape-stryker-karl-storz-sst-or-black-box-artisight-proximie-and-apella

---

*Figures are drawn from public sources (cited above); market-sizing bottom-up
assumptions are illustrative and labeled as such. Argus is a decision-support
prototype — every alert is a possible event requiring human confirmation; it is
not a medical device and makes no clinical claims.*
