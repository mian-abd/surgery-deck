"""Exercise every Gemini capability without running the server.

Verifies the API key, the model id, multimodal upload, and JSON-schema parsing
before any of it is wired into a live demo.

    cd backend
    $env:PYTHONPATH = "."
    .\.venv\Scripts\python.exe tools\gemini_test.py
"""
import asyncio
import glob
import os
import sys

from app import gemini


def _an_evidence_frame() -> bytes | None:
    """Use a real saved evidence JPEG if one exists, else synthesize a scene."""
    files = sorted(glob.glob(os.path.join("evidence", "*.jpg")), key=os.path.getmtime)
    if files:
        print(f"  using evidence frame: {os.path.basename(files[-1])}")
        with open(files[-1], "rb") as f:
            return f.read()
    try:
        import cv2
        import numpy as np

        img = np.full((540, 960, 3), (52, 50, 56), dtype=np.uint8)
        cv2.rectangle(img, (580, 90), (930, 500), (150, 112, 74), -1)
        cv2.putText(img, "STERILE FIELD", (590, 80), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (220, 220, 220), 1)
        cv2.rectangle(img, (30, 300), (250, 510), (78, 92, 108), -1)
        cv2.putText(img, "NON-STERILE", (35, 292), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (220, 220, 220), 1)
        cv2.rectangle(img, (80, 380), (200, 400), (205, 205, 210), -1)
        print("  using synthesized scene (no evidence/*.jpg found)")
        ok, buf = cv2.imencode(".jpg", img)
        return buf.tobytes() if ok else None
    except Exception:
        return None


async def main() -> int:
    print(f"gemini.available() = {gemini.available()}")
    print(f"status = {gemini.status()}")
    if not gemini.available():
        print("\nNo GEMINI_API_KEY. Put it in backend/.env as:\n"
              "  GEMINI_API_KEY=your_key_here\n"
              "(That file is gitignored. Everything degrades gracefully without it.)")
        return 1

    frame = _an_evidence_frame()
    failures = 0

    print("\n--- 1+2. event narration + multimodal verification ---")
    out = await gemini.enrich_event(
        {
            "event_type": "sterile_breach",
            "severity": "critical",
            "title": "Possible sterile-field contamination: clamp #5",
            "rule_description": "A potentially contaminated instrument re-entered "
                                "the sterile field.",
            "rule_confidence": 0.9,
            "detail": {"track_id": 5, "zone": "sterile", "previous_zone": "nonsterile"},
        },
        frame,
    )
    if out:
        for k, v in out.items():
            print(f"  {k}: {v}")
    else:
        print("  FAILED (returned None)")
        failures += 1

    print("\n--- 3. end-of-session summary ---")
    summary = await gemini.summarize_session(
        {
            "procedure": "Simulated Appendectomy",
            "room": "Demo OR 1",
            "duration_minutes": 18.0,
            "initial_counts": {"forceps": 2, "scissors": 2, "clamp": 1, "scalpel": 1},
            "final_counts": {"forceps": 1, "scissors": 2, "clamp": 1, "scalpel": 1},
            "count_difference": {"forceps": 1},
            "hygiene_observed": 1,
            "hygiene_violations": 1,
            "sterile_breaches": 2,
            "critical": 2,
            "warnings": 2,
            "unreviewed": 3,
            "events": [
                {"time": "10:04:18", "type": "hygiene_missing", "severity": "warning",
                 "title": "Possible hand-hygiene noncompliance — Staff-02",
                 "review_status": "pending"},
                {"time": "10:08:42", "type": "sterile_breach", "severity": "critical",
                 "title": "Possible sterile-field contamination: clamp #5",
                 "review_status": "pending"},
                {"time": "10:19:02", "type": "count_mismatch", "severity": "critical",
                 "title": "Count mismatch: 1 forceps unaccounted for",
                 "review_status": "pending"},
            ],
        },
        cache_key="test-session",
        event_count=3,
    )
    if summary:
        print(f"  summary: {summary.get('summary')}")
        for r in summary.get("key_risks", []):
            print(f"  risk: {r}")
    else:
        print("  FAILED (returned None)")
        failures += 1

    print("\n--- 4. zone suggestions (multimodal) ---")
    if frame:
        zones = await gemini.suggest_zones(frame)
        if zones is None:
            print("  FAILED (returned None)")
            failures += 1
        else:
            print(f"  {len(zones)} zone(s) proposed")
            for z in zones:
                pts = ", ".join(f"[{p[0]:.2f},{p[1]:.2f}]" for p in z["polygon"][:4])
                print(f"  - {z['zone_type']:<11} {z['name']}: {pts}")
    else:
        print("  skipped (no frame available)")

    print(f"\n{'ALL GEMINI CAPABILITIES OK' if not failures else f'{failures} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
