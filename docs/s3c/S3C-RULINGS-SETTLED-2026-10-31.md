# S3c settled rulings — 2026-10-31

Q1 Calendar circle / leap day:
Seasonal eligibility uses a 366-slot leap-year month-day circle; Feb 29 has its own slot; windows wrap across year boundaries. Ruling 6 and the 20-day floors still apply after admission.

Q2 Hinge variance / condition number:
A hinge is near-zero when its fit-stratum standard deviation is below 1e-10 times the response standard deviation over the same stratum, or when it takes fewer than 2 distinct values. The Ruling 4 condition number is computed on X exactly as supplied to the solver; the receipt must name the matrix used.

Q3 NWS interval:
The alert interval is [onset, ends] when ends is present, otherwise [onset, expires]; if onset is missing, use effective as the start. Ruling 7's half-open overlap mapping is unchanged. Alerts remain annotation-only.

Issuance freeze:
Issuance cutoff 7:00 AM ET. For a forecast issued on day D, D-2 is the latest completed peak. Prospective mode uses only data with availability time at or before issuance and fails closed when availability cannot be verified. Retrospective mode remains available and labeled.

---

Amendment, Nov 5, 2026 (appended; the settled rulings above are not rewritten):

**Darren's ruling, Nov 5, 2026 (02:19 ET): SAME-DAY — the 07:00 job forecasts today's peak; freshness judged on completed history through target − 2.**

What it changes: the issue-time gate only. `target_date` is the issue day D, and a prospective forecast must be issued at or before the 07:00 America/New_York cutoff on the target day and before that day's peak. Issuance after that is an UNSCORED no-call. This replaces the before-the-target-date boundary that `issue_time_not_before_target_date` enforced (`docs/s3c/S3C-DIAGNOSIS-2026-10-31.md`, line 28), which the Issuance freeze paragraph above did not itself set.

What it leaves unchanged: the Issuance freeze paragraph stands as written. Cutoff 7:00 AM ET; for a forecast issued on day D, D-2 is the latest completed peak; prospective mode uses only data with availability at or before issuance and fails closed when availability cannot be verified; retrospective mode remains available and labeled. Under same-day, D-2 equals target − 2, so freshness is judged on completed history through target − 2 and never on the target day's own load row. Q1 to Q3 are untouched.
