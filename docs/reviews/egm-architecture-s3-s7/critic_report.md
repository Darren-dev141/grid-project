# Stage 7: Critic Review (egm-design, egm-structural, egm-style)

Target: `docs/architecture-s3-s7.md`, FeatureRange lines 1-151.
Standard: `feature-spec-standard.md` for design and structural.
Reviewer status: design completed, structural completed, style completed.
Uninterrupted mode, one round, no fixes applied yet.

Raw counts:

| Reviewer | Blocker | Major | Nit |
| --- | --- | --- | --- |
| Design | 2 | 7 | 6 |
| Structural | 1 | 6 | 7 |
| Style | 0 | 8 | 14 |

Duplicate findings are merged below. IDs are `<reviewer>-1-<n>`.

## Blockers

- **C1. Receipt timestamps are self-reported, so the "nothing to cherry-pick" claim fails** (design-1-1; lines 23, 45-48, 89, 92, 96, 131-138).
  - **Exploit:** after a day settles, add a receipt dated 23:59 the night before. `verify` accepts it, and the "latest before the day starts" rule makes it the receipt of record.
  - **Fix:**
    - CI rejects any newly added receipt whose target day has already started by CI's own clock.
    - Record a time the writer does not control.
    - Make `verify` check that time.
- **C2. A fresh Actions runner has no warehouse or raw history** (design-1-2; lines 27-35, 130). This repeats Stage 5 Blocker 1. NWS issuances cannot be fetched again, and NCEI allows at most 366 days per request.
- **C3. No problem statement or motivation** (structural-1-1; lines 1-16). This overlaps the Stage 6 major on missing goals.

## Majors

- **C4. Required sections from the standard are missing** (design-1-3, structural-1-2/3/4):
  - goals and non-goals;
  - a success measure (beat a climatology or persistence baseline);
  - an "Alternatives Considered" section (A gets 2 lines, and its critique isn't linked);
  - one Risks section covering failure modes, security and scale.
- **C5. The `ledger verify` CI wiring is inconsistent and can be bypassed** (design-1-4, style-1-3):
  - `--since` contradicts "full log".
  - `--diff-filter` skips merge commits.
  - The manual commit step contradicts "one scheduled run".
  - Pushes made with `GITHUB_TOKEN` don't trigger other workflows.
  - There is no concurrency group, cron runs can be delayed, the run time is unset, and token permissions are unstated.
- **C6. Failures other than stale input are unhandled** (design-1-5, structural-1-4):
  - One failing dbt test aborts the run before `ledger.append`, so no receipt is written.
  - A crash after the append can leave a receipt that is never pushed.
- **C7. The complete-day rule is wrong on DST days** (design-1-6).
  - "23, 24 or 25 ok hours" should be "that date's expected hour count".
  - An `implausible` peak hour can make the actual peak wrong.
- **C8. The weather used for fitting differs from the weather used for forecasting** (design-1-7).
  - Location: the BWI station versus the Reisterstown gridpoint, about 35 km apart.
  - Daily definition: calendar-day TMAX/TMIN versus daytime high and night-start low.
- **C9. "One new file" for PJM is unsupported** (design-1-8, structural-1-6, style-1-2; overlaps Stage 5 Major 5). Gaps:
  - no thresholds for external level scoring;
  - no discovery mechanism;
  - `forecasters/` is not in the module map;
  - it conflicts with line 149;
  - a key secret is needed.
- **C10. Scores and scorecards are not frozen** (design-1-9). EIA revisions can change published weekly results after the fact. `settle_days` has no value.
- **C11. The command surface is inconsistent** (structural-1-5/7, style-1-1, design-1-12): "three commands" versus `replay`, and the other console scripts have no stated fate.
- **C12. The types are undefined** (structural-1-8). The receipt uses ad hoc notation with no value types or timestamp format. `Report` and `Violation` are missing.
- **C13. Version numbering collides** (style-1-4/5, overlaps Stage 6 Major 3): v0, v1 and v2 for the index, plus "v1" for the retired product.
- **C14. The "never rescore" claim is too strong** (style-1-6). Only `thresholds_mw` is frozen. The scoring tolerance and settle days live in the definition.
- **C15. The comparison is one-sided** (style-1-7, design-1-13): dbt cost is measured, Python cost is asserted, and the doc uses slogans.
- **C16. BGE and "trailing color" are jargon** (style-1-8).

## Nits (merged)

- "Canonical JSON" is undefined. Specify RFC 8785 or an exact `json.dumps` configuration.
- No-call precedence is undefined: a later stale no-call outranks an earlier valid call.
- Residual against temperature is promised but not in the scorecard signature.
- NCEI is missing from the fetch window and from freshness.
- The geography label "PJM RTO" doesn't match "PJM balancing authority" in the model.
- Code fences have no language tags. Signature typing is inconsistent.
- Cross-references aren't links. Measured claims don't link their evidence.
- Future tense is used for work already done ("Adding `ncei` edits that set").
- "Gaps, handled" lists an unhandled gap. Line wrapping is inconsistent.
- Wording:
  - "S3a", "Darren", "settled days" and "ok hours" are used undefined.
  - "late issue" collides with "GitHub issue".
  - "if you decline" switches to second person.
  - "the name certifies the content" overstates a 12-character prefix.
