# Stage 8: Intermediate Zoom Out (egm-zoom-out)

Target: `docs/architecture-s3-s7.md`, full file. Reviewer status: completed.
Focus: whether the fixes proposed in Stages 5-7 over-build the design.

Verdict: the earlier stages found real blockers. But applying all ~70 proposed fixes
would turn this doc into a second plan that duplicates `PLAN.md`. Each blocker can
be fixed by deleting or rewording a few lines. None needs new machinery.

## Blockers

1. **`PLAN.md` v3 copies the flawed mechanics word for word.** Its lines 29, 31, 33 and 58 repeat four of them:
   - required check plus pre-commit hook;
   - the push event as the timestamp;
   - "one new file" for PJM;
   - "latest before the day".

   Fixing only this doc leaves the two documents contradicting each other. Mirror the mechanics fixes into `PLAN.md`. Point to `PLAN.md` for decisions and goals instead of restating them.
2. **Runner state: rebuild, don't archive.**
   - The fit needs NCEI history and EIA demand. Both can be fetched again cheaply: about 14 EIA pages plus about 8 NCEI requests.
   - Each run needs only the current NWS issuance.
   - So the warehouse is rebuilt every run, the Actions cache only speeds that up, and the ledger is the only durable state.
   - Tradeoff: on Actions, past NWS issuances are not kept between runs. The receipt carries the driver values it used.
3. **One change fixes both branch protection and backdating:**
   - Drop "required check". Branch protection blocks only force-push and deletion.
   - Run `ledger verify` inside the daily job before it pushes, and in CI on every push as a check that fails loudly but isn't required.
   - A newly added receipt fails if its target day has already started by the verifying run's clock.
   - Put each receipt's filename and hash in the pinned-issue comment.
   - Reject a GitHub API verifier, RFC 3161/OpenTimestamps and a receipts branch.
   - Change "nothing to cherry-pick" to "a backdated receipt is detected".

## Majors

4. **Disagrees with Stage 5 Nit 7.** Keep two scopes: the full history for non-add changes and hash mismatches, and the pushed range for late adds. Checking full history against today's clock would flag every old receipt.
5. **C3 downgraded to Major. C4's new sections are scope creep.** Add a two-line objective that links `PLAN.md`. Do not add Goals/Non-goals, Alternatives or Risks sections. A baseline forecaster is new product scope, so route it to the owner.
6. **C6: use one scorecard rule.** A target date with no receipt of record counts as a miss. That covers a build failure, a crash after append and an outage, with no new enum values or recovery protocol.
7. **Fix the outdated status by deleting:**
   - the "if you decline" fallback (which also fixes v0/v1);
   - the Task Scheduler bullet;
   - the manual commit and push;
   - the Owner decisions section, replaced by a link to `PLAN.md`.

## Nits

8. Delete the PJM "one new file" paragraph. Keep `forecaster_id`. Discovery and null rules are YAGNI.
9. Instead of specifying canonical JSON, say the hash covers the file's bytes as written. Use "identifies", not "certifies".
10. Replace the receipt notation with one example receipt. Leave type field lists to the code.
11. Workflow YAML details belong to S4/S5. Here, only state an early enough run time.
12. C14: one sentence, "score uses the definition named in the receipt". C10: post the weekly scorecard as an issue comment. No score ledger.
13. Extend `cli.py` (`grid replay <source>`). Keep the other console scripts and remove only `grid-publish`.
14. Deploy Pages from an artifact. Commit only `ledger/`. Pages can't serve a `site/` folder.
15. Drop the pre-commit hook, here and in `PLAN.md`.
16. Fit/forecast weather: the S3c gate covers it. If the location matters, change the NWS point constant.
17. Write the retirement scope as "everything that serves price or Power BI", not a file list.
18. `nws_forecast_latest`: either leave it or delete it at S5. Drop "the docs say so".
