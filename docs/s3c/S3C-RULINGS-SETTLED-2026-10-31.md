# S3c settled rulings — 2026-10-31

Q1 Calendar circle / leap day:
Seasonal eligibility uses a 366-slot leap-year month-day circle; Feb 29 has its own slot; windows wrap across year boundaries. Ruling 6 and the 20-day floors still apply after admission.

Q2 Hinge variance / condition number:
A hinge is near-zero when its fit-stratum standard deviation is below 1e-10 times the response standard deviation over the same stratum, or when it takes fewer than 2 distinct values. The Ruling 4 condition number is computed on X exactly as supplied to the solver; the receipt must name the matrix used.

Q3 NWS interval:
The alert interval is [onset, ends] when ends is present, otherwise [onset, expires]; if onset is missing, use effective as the start. Ruling 7's half-open overlap mapping is unchanged. Alerts remain annotation-only.

Issuance freeze:
Issuance cutoff 7:00 AM ET. For a forecast issued on day D, D-2 is the latest completed peak. Prospective mode uses only data with availability time at or before issuance and fails closed when availability cannot be verified. Retrospective mode remains available and labeled.
