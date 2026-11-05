/-
Grid issuance ledger + data-freshness model — core Lean 4.35.0, NO Mathlib.

WHAT THIS MODELS
The S3c daily issuance cadence of the grid project as it actually ran
Nov 1–3, 2026, at the level of its tracker/ledger discipline
(PC repo `docs/s3c/CADENCE-TRACKER.md`, receipts in `docs/s3c/*.json`),
specified against the plan of record (`~/workspace/grid-project/PLAN.md` v3).

The ledger is a list of day-records, one per day-slot, appended in slot
order. A record's outcome is one of:
  * `scored`      — a scored call was issued for the day;
  * `noCall r`    — the canonical pipeline ran and wrote a no-call receipt
                    with reason `r` (e.g. `staleLoad`);
  * `missed`      — the day resolved with no receipt (crash / no issuance).

Each record carries the fields the real receipts and tracker carry or the
failure history made necessary: the hash of the artifact that executed,
the environment id, the stress-definition hash frozen at issue time, the
latest input day used (its "stamp"), the TRUE issue time, and whether
input availability was verified.

The Config is stated ONCE (canonical artifact hash, pinned environment,
freshness bound, first slot day). There is no step that changes the
Config, and no step that edits an existing record: steps only append.
That is the formal content of "one environment, stated once" and of the
no-backfill ruling.

FAILURES THIS SPEAKS TO (see SPEC.md for the full mapping)
  * Nov 1, 2026 — the 07:00 slot executed a STALE COPY of the issuance
    script (AppData hermes copy, not the repo copy) and died at imports;
    no receipt; the failure alert was suppressed.
  * Nov 1 (late) / Nov 2 — receipts written but UNSCORED no-calls,
    reason `staleLoad` (inputs older than the D-2 ceiling; input
    availability unverified). Darren's ruling: the day counts in the
    ISSUANCE streak; the SCORED cadence does not move.
  * Nov 3, 2026 — issuance died on a cross-environment split: pinned
    duckdb 1.4.4 sat in repo-root `.venv-cadence/` while the cadence
    interpreter imports from `autopilot/.venv`. Third unscored day.

TIME MODEL: days and minutes are natural numbers from a fixed epoch.
`scheduled d = d * 1440 + 420` is the 07:00 local slot of day `d`.
(Scheduler timezone/DST behaviour is outside the model — assumption A2
in SPEC.md.)
-/

/-- Reasons a day can end in a no-call receipt. Mirrors the receipt
    field `no_call_reason` (`stale_load`, `stale_weather`) plus the
    S3c rulings' insufficient-history unscored case. -/
inductive NoCallReason where
  | staleLoad
  | staleWeather
  | insufficientHistory
deriving DecidableEq, Repr

/-- The outcome recorded for one day-slot. `scored` carries an opaque
    payload standing for the frozen call content (peak/level). -/
inductive Outcome where
  | scored (call : Nat)
  | noCall (reason : NoCallReason)
  | missed
deriving DecidableEq, Repr

/-- One day-slot's ledger record. Hashes and ids are abstract naturals:
    the model proves equality/inequality facts about them, not
    cryptographic facts (assumption A1 in SPEC.md). -/
structure DayRecord where
  day : Nat
  outcome : Outcome
  artifactHash : Nat
  envId : Nat
  defHash : Nat
  inputStamp : Option Nat
  issuedAt : Nat
  availVerified : Bool
deriving DecidableEq, Repr

/-- The cadence configuration, stated once for the whole ledger:
    the canonical artifact's hash, the one pinned environment's id,
    the freshness bound in days (2 — the recorded "D-2 ceiling"), and
    the day number of the ledger's first slot. Deliberately carries NO
    "current definition" field: a definition version lives only on the
    records issued under it, so no later amendment can rewrite what an
    old record says (invariant I6). -/
structure Config where
  canonicalHash : Nat
  envId : Nat
  freshBound : Nat
  firstDay : Nat
deriving DecidableEq, Repr

/-- The scheduled instant of day `d`'s slot: 07:00 local, in minutes
    from the epoch. -/
def scheduled (day : Nat) : Nat := day * 1440 + 420

/-- Lateness is DERIVED from a record's own fields, never asserted:
    a record is late iff its true issue time is after its slot. -/
def IsLate (r : DayRecord) : Prop := scheduled r.day < r.issuedAt

/-- The per-outcome conditions under which a record may be appended.
    Receipt-producing outcomes (`scored`, `noCall`) must come from the
    canonical artifact running in the pinned environment. A `scored`
    outcome additionally requires verified input availability and a
    fresh, no-lookahead input stamp: strictly before the target day
    (S3c Ruling 6: the fitting pool for day D is days strictly before D)
    and no older than the freshness bound (`day ≤ stamp + freshBound`,
    the D-2 ceiling). A `missed` record is unconstrained beyond the
    common conditions in `StepOK` — it names whatever ran and failed. -/
def OutcomeOK (cfg : Config) (r : DayRecord) : Outcome → Prop
  | .scored _ =>
      r.artifactHash = cfg.canonicalHash ∧ r.envId = cfg.envId ∧
      r.availVerified = true ∧
      ∃ s, r.inputStamp = some s ∧ s < r.day ∧ r.day ≤ s + cfg.freshBound
  | .noCall _ =>
      r.artifactHash = cfg.canonicalHash ∧ r.envId = cfg.envId
  | .missed => True

/-- One append step: the record closes the NEXT slot in order
    (`day = firstDay + current length` — slots are neither skipped nor
    repeated), it is never stamped earlier than its slot (no backdating;
    the launcher likewise refuses pre-07:00 issuance), and its outcome
    satisfies `OutcomeOK`. -/
def StepOK (cfg : Config) (l : List DayRecord) (r : DayRecord) : Prop :=
  r.day = cfg.firstDay + l.length ∧
  scheduled r.day ≤ r.issuedAt ∧
  OutcomeOK cfg r r.outcome

/-- Reachable ledgers: built from empty by `StepOK` appends only.
    Existing records are never modified — there is no other constructor. -/
inductive Reachable (cfg : Config) : List DayRecord → Prop where
  | init : Reachable cfg []
  | step {l : List DayRecord} {r : DayRecord} :
      Reachable cfg l → StepOK cfg l r → Reachable cfg (l ++ [r])

/-- One reachable ledger extending another by appends only. -/
inductive Extends (cfg : Config) (l : List DayRecord) : List DayRecord → Prop where
  | refl : Extends cfg l l
  | step {l' : List DayRecord} {r : DayRecord} :
      Extends cfg l l' → StepOK cfg l' r → Extends cfg l (l' ++ [r])

/-! ## Per-record invariants -/

/-- The conjunction every record of a reachable ledger satisfies:
    never stamped before its slot; receipts carry the canonical
    artifact hash and the pinned env id; scored records were fresh,
    no-lookahead, and availability-verified. -/
def RecordProps (cfg : Config) (r : DayRecord) : Prop :=
  scheduled r.day ≤ r.issuedAt ∧
  (r.outcome = Outcome.missed ∨
    (r.artifactHash = cfg.canonicalHash ∧ r.envId = cfg.envId)) ∧
  (∀ c, r.outcome = Outcome.scored c →
    r.availVerified = true ∧
    ∃ s, r.inputStamp = some s ∧ s < r.day ∧ r.day ≤ s + cfg.freshBound)

theorem record_props {cfg : Config} {l : List DayRecord} (h : Reachable cfg l) :
    ∀ r ∈ l, RecordProps cfg r := by
  induction h with
  | init => intro r hr; simp at hr
  | step hl hstep ih =>
      rename_i l₀ r₀
      intro r hr
      rw [List.mem_append] at hr
      rcases hr with hr | hr
      · exact ih r hr
      · rw [List.mem_singleton] at hr
        subst hr
        obtain ⟨-, htime, hout⟩ := hstep
        refine ⟨htime, ?_, ?_⟩
        · cases ho : r.outcome with
          | missed => exact Or.inl rfl
          | scored c =>
              have h2 : r.artifactHash = cfg.canonicalHash ∧ r.envId = cfg.envId ∧
                  r.availVerified = true ∧
                  ∃ s, r.inputStamp = some s ∧ s < r.day ∧
                    r.day ≤ s + cfg.freshBound := by
                rw [ho] at hout; exact hout
              exact Or.inr ⟨h2.1, h2.2.1⟩
          | noCall reason =>
              have h2 : r.artifactHash = cfg.canonicalHash ∧
                  r.envId = cfg.envId := by
                rw [ho] at hout; exact hout
              exact Or.inr h2
        · intro c hc
          have h2 : r.artifactHash = cfg.canonicalHash ∧ r.envId = cfg.envId ∧
              r.availVerified = true ∧
              ∃ s, r.inputStamp = some s ∧ s < r.day ∧
                r.day ≤ s + cfg.freshBound := by
            rw [hc] at hout; exact hout
          exact ⟨h2.2.2.1, h2.2.2.2⟩

/-- I2 + I4 (receipt half): every receipt in a reachable ledger was
    produced by the canonical artifact in the pinned environment.
    The Nov 1 stale copy and the Nov 3 split environment are both
    outside this set — in the model, such runs cannot produce receipts. -/
theorem receipt_hash_env {cfg : Config} {l : List DayRecord} (h : Reachable cfg l)
    {r : DayRecord} (hr : r ∈ l) (hrec : r.outcome ≠ Outcome.missed) :
    r.artifactHash = cfg.canonicalHash ∧ r.envId = cfg.envId := by
  have hp := (record_props h r hr).2.1
  rcases hp with hmiss | hok
  · exact absurd hmiss hrec
  · exact hok

/-- I1: a scored record's inputs were availability-verified, strictly
    before the target day, and within the freshness bound. The Nov 1
    and Nov 2 configurations (stale stamp, availability unverified)
    cannot appear as scored records — see the refusal example below. -/
theorem scored_fresh {cfg : Config} {l : List DayRecord} (h : Reachable cfg l)
    {r : DayRecord} (hr : r ∈ l) {c : Nat} (hsc : r.outcome = Outcome.scored c) :
    r.availVerified = true ∧
    ∃ s, r.inputStamp = some s ∧ s < r.day ∧ r.day ≤ s + cfg.freshBound :=
  (record_props h r hr).2.2 c hsc

/-- I8: no record is stamped before its slot — no backdating. -/
theorem never_early {cfg : Config} {l : List DayRecord} (h : Reachable cfg l)
    {r : DayRecord} (hr : r ∈ l) :
    scheduled r.day ≤ r.issuedAt :=
  (record_props h r hr).1

/-! ## Slot order, uniqueness, persistence -/

/-- Every record sits in its slot window: days in a reachable ledger of
    length n are exactly `firstDay, firstDay+1, …, firstDay+n-1` in
    order (bounds form; see also `day_surjective`). -/
theorem day_bounds {cfg : Config} {l : List DayRecord} (h : Reachable cfg l) :
    ∀ r ∈ l, cfg.firstDay ≤ r.day ∧ r.day < cfg.firstDay + l.length := by
  induction h with
  | init => intro r hr; simp at hr
  | step hl hstep ih =>
      rename_i l₀ r₀
      intro r hr
      obtain ⟨hday, -, -⟩ := hstep
      have hlen : List.length [r₀] = 1 := rfl
      rw [List.length_append]
      rw [List.mem_append] at hr
      rcases hr with hr | hr
      · have hb := ih r hr
        omega
      · rw [List.mem_singleton] at hr
        subst hr
        omega

/-- Days strictly increase along the ledger. -/
theorem pairwise_days {cfg : Config} {l : List DayRecord} (h : Reachable cfg l) :
    List.Pairwise (fun a b : DayRecord => a.day < b.day) l := by
  induction h with
  | init => exact List.Pairwise.nil
  | step hl hstep ih =>
      rename_i l₀ r₀
      obtain ⟨hday, -, -⟩ := hstep
      rw [List.pairwise_append]
      refine ⟨ih, ?_, ?_⟩
      · exact List.Pairwise.cons (fun b hb => by simp at hb) List.Pairwise.nil
      · intro x hx y hy
        rw [List.mem_singleton] at hy
        subst hy
        show x.day < y.day
        have hb := (day_bounds hl) x hx
        omega

/-- A day has at most one record in a strictly day-increasing list. -/
theorem day_unique : ∀ {l : List DayRecord},
    List.Pairwise (fun a b : DayRecord => a.day < b.day) l →
    ∀ {a b : DayRecord}, a ∈ l → b ∈ l → a.day = b.day → a = b := by
  intro l
  induction l with
  | nil => intro _ a b ha; simp at ha
  | cons hd t ih =>
      intro hp a b ha hb hday
      rw [List.pairwise_cons] at hp
      obtain ⟨hrel, hpt⟩ := hp
      rcases List.mem_cons.mp ha with rfl | ha'
      · rcases List.mem_cons.mp hb with rfl | hb'
        · rfl
        · have hlt : a.day < b.day := hrel b hb'
          simp [hday] at hlt
      · rcases List.mem_cons.mp hb with rfl | hb'
        · have hlt : b.day < a.day := hrel a ha'
          simp [hday] at hlt
        · exact ih hpt ha' hb' hday

/-- Every slot in the ledger's range has a record: no silent slots.
    (The model half of invariant I7 — the record exists. Whether the
    outside world was told is the alerting half, in CONFORMANCE.md.) -/
theorem day_surjective {cfg : Config} {l : List DayRecord} (h : Reachable cfg l) :
    ∀ d, cfg.firstDay ≤ d → d < cfg.firstDay + l.length →
      ∃ r ∈ l, r.day = d := by
  induction h with
  | init =>
      intro d h1 h2
      simp only [List.length_nil, Nat.add_zero] at h2
      omega
  | step hl hstep ih =>
      rename_i l₀ r₀
      intro d h1 h2
      obtain ⟨hday, -, -⟩ := hstep
      have hlen : List.length [r₀] = 1 := rfl
      rw [List.length_append] at h2
      by_cases hlt : d < cfg.firstDay + l₀.length
      · obtain ⟨x, hx, hxd⟩ := ih d h1 hlt
        exact ⟨x, List.mem_append_left _ hx, hxd⟩
      · have hd : d = cfg.firstDay + l₀.length := by omega
        refine ⟨r₀, ?_, ?_⟩
        · exact List.mem_append_right _ (List.mem_singleton_self r₀)
        · rw [hday, hd]

/-! ## Lookup: the destination-side view of the ledger -/

/-- First-match lookup of a day's record — the tracker's view when a
    score is claimed: a day counts only through the record found here. -/
def lookupDay : List DayRecord → Nat → Option DayRecord
  | [], _ => none
  | r :: t, d => if r.day = d then some r else lookupDay t d

theorem or_some_left (r : DayRecord) (x : Option DayRecord) :
    (some r).or x = some r := rfl

theorem or_none_left (x : Option DayRecord) :
    (none : Option DayRecord).or x = x := rfl

theorem lookupDay_append (a b : List DayRecord) (d : Nat) :
    lookupDay (a ++ b) d = (lookupDay a d).or (lookupDay b d) := by
  induction a with
  | nil => exact or_none_left _
  | cons x t ih =>
      show lookupDay (x :: (t ++ b)) d = (lookupDay (x :: t) d).or (lookupDay b d)
      simp only [lookupDay]
      by_cases hc : x.day = d
      · rw [ite_eq_left hc, ite_eq_left hc, or_some_left]
      · rw [ite_eq_right hc, ite_eq_right hc, ih]

theorem lookupDay_none_of_absent : ∀ {l : List DayRecord} {d : Nat},
    (∀ r ∈ l, r.day ≠ d) → lookupDay l d = none := by
  intro l
  induction l with
  | nil => intro _ _; rfl
  | cons x t ih =>
      intro d h
      simp only [lookupDay]
      rw [ite_eq_right (h x List.mem_cons_self),
        ih (fun r hr => h r (List.mem_cons_of_mem x hr))]

theorem lookupDay_spec {l : List DayRecord} {d : Nat} {r : DayRecord}
    (h : lookupDay l d = some r) : r.day = d ∧ r ∈ l := by
  induction l with
  | nil => simp [lookupDay] at h
  | cons x t ih =>
      simp only [lookupDay] at h
      by_cases hc : x.day = d
      · rw [ite_eq_left hc] at h
        have hx : x = r := Option.some.inj h
        subst hx
        exact ⟨hc, List.mem_cons_self⟩
      · rw [ite_eq_right hc] at h
        obtain ⟨h1, h2⟩ := ih h
        exact ⟨h1, List.mem_cons_of_mem x h2⟩

/-- In a day-unique list, a present record is THE record lookup finds. -/
theorem lookup_of_mem_unique : ∀ {l : List DayRecord},
    (∀ a b : DayRecord, a ∈ l → b ∈ l → a.day = b.day → a = b) →
    ∀ {r : DayRecord}, r ∈ l → lookupDay l r.day = some r := by
  intro l
  induction l with
  | nil => intro _ r hr; simp at hr
  | cons x t ih =>
      intro hu r hr
      simp only [lookupDay]
      by_cases hc : x.day = r.day
      · rw [ite_eq_left hc]
        have hxr : x = r := hu x r List.mem_cons_self hr hc
        rw [hxr]
      · rw [ite_eq_right hc]
        apply ih
        · intro a b ha hb hd
          exact hu a b (List.mem_cons_of_mem x ha) (List.mem_cons_of_mem x hb) hd
        · rcases List.mem_cons.mp hr with rfl | hr'
          · exact (hc rfl).elim
          · exact hr'

/-! ## Extension: nothing already recorded can change -/

theorem extends_reachable {cfg : Config} {l l' : List DayRecord}
    (h : Extends cfg l l') (hl : Reachable cfg l) : Reachable cfg l' := by
  induction h with
  | refl => exact hl
  | step hext hstep ih => exact Reachable.step ih hstep

/-- Append-only, stated as prefix: any extension of the ledger has the
    original ledger as a prefix. -/
theorem extends_prefix {cfg : Config} {l l' : List DayRecord}
    (h : Extends cfg l l') : List.IsPrefix l l' := by
  induction h with
  | refl => exact ⟨[], List.append_nil l⟩
  | step hext hstep ih =>
      rename_i l₀ r₀
      obtain ⟨t, ht⟩ := ih
      exact ⟨t ++ [r₀], by rw [← List.append_assoc, ht]⟩

/-- Whole-record persistence: lookup in any extension returns the same
    record. This is also the proof behind I6 (definition freeze): the
    `defHash` a record was issued with is the `defHash` it keeps,
    because the whole record is the thing that persists. -/
theorem lookupDay_persistent {cfg : Config} {l l' : List DayRecord}
    (h : Extends cfg l l') {d : Nat} {r : DayRecord}
    (hr : lookupDay l d = some r) : lookupDay l' d = some r := by
  induction h with
  | refl => exact hr
  | step hext hstep ih =>
      rw [lookupDay_append, ih, or_some_left]

/-- Every slot day in range resolves to a record via lookup. -/
theorem lookupDay_complete {cfg : Config} {l : List DayRecord}
    (h : Reachable cfg l) {d : Nat}
    (h1 : cfg.firstDay ≤ d) (h2 : d < cfg.firstDay + l.length) :
    ∃ r, lookupDay l d = some r ∧ r.day = d := by
  obtain ⟨r, hr, hrd⟩ := day_surjective h d h1 h2
  have hu : ∀ a b : DayRecord, a ∈ l → b ∈ l → a.day = b.day → a = b :=
    fun a b ha hb hd => day_unique (pairwise_days h) ha hb hd
  refine ⟨r, ?_, hrd⟩
  rw [← hrd]
  exact lookup_of_mem_unique hu hr

/-- I5 (no backfill): a day recorded `missed` can never acquire a
    different record in any extension of the ledger. The missed record
    found by lookup persists, days are unique, so no later append can
    become that day's record — in particular it can never become a
    scored record retroactively. -/
theorem no_backfill {cfg : Config} {l l' : List DayRecord}
    (hl : Reachable cfg l) (h : Extends cfg l l')
    {r r' : DayRecord} (hr : r ∈ l) (hr' : r' ∈ l') (hd : r'.day = r.day)
    (_hmiss : r.outcome = Outcome.missed) : r = r' := by
  have hl' : Reachable cfg l' := extends_reachable h hl
  have hu : ∀ a b : DayRecord, a ∈ l → b ∈ l → a.day = b.day → a = b :=
    fun a b ha hb hd => day_unique (pairwise_days hl) ha hb hd
  have hu' : ∀ a b : DayRecord, a ∈ l' → b ∈ l' → a.day = b.day → a = b :=
    fun a b ha hb hd => day_unique (pairwise_days hl') ha hb hd
  have h1 : lookupDay l' r.day = some r :=
    lookupDay_persistent h (lookup_of_mem_unique hu hr)
  have h2 : lookupDay l' r.day = some r' := by
    have h3 := lookup_of_mem_unique hu' hr'
    rwa [hd] at h3
  rw [h1] at h2
  exact Option.some.inj h2

/-! ## The two ledgers: issuance streak vs scored cadence -/

/-- Per-outcome contribution to the SCORED cadence. -/
def scoreVal : Outcome → Nat
  | .scored _ => 1
  | _ => 0

/-- Per-outcome contribution to the ISSUANCE streak (receipts only:
    scored and no-call days; a missed day issues nothing). -/
def receiptVal : Outcome → Nat
  | .scored _ => 1
  | .noCall _ => 1
  | .missed => 0

def countWith (f : Outcome → Nat) : List DayRecord → Nat
  | [] => 0
  | r :: t => f r.outcome + countWith f t

/-- The scored cadence: the count behind the S7 gate's 14. -/
def scoredCadence (l : List DayRecord) : Nat := countWith scoreVal l

/-- The issuance streak: every day that produced a receipt. -/
def receiptStreak (l : List DayRecord) : Nat := countWith receiptVal l

theorem countWith_append (f : Outcome → Nat) (a b : List DayRecord) :
    countWith f (a ++ b) = countWith f a + countWith f b := by
  induction a with
  | nil => simp [countWith]
  | cons x t ih => simp [countWith, List.cons_append, ih, Nat.add_assoc]

theorem countWith_step (f : Outcome → Nat) (l : List DayRecord) (r : DayRecord) :
    countWith f (l ++ [r]) = countWith f l + f r.outcome := by
  rw [countWith_append]
  simp [countWith]

theorem scoredCadence_step (l : List DayRecord) (r : DayRecord) :
    scoredCadence (l ++ [r]) = scoredCadence l + scoreVal r.outcome :=
  countWith_step _ _ _

theorem receiptStreak_step (l : List DayRecord) (r : DayRecord) :
    receiptStreak (l ++ [r]) = receiptStreak l + receiptVal r.outcome :=
  countWith_step _ _ _

theorem countWith_le (f g : Outcome → Nat) (hfg : ∀ o, f o ≤ g o)
    (l : List DayRecord) : countWith f l ≤ countWith g l := by
  induction l with
  | nil => exact Nat.le.refl
  | cons x t ih =>
      simp only [countWith]
      exact Nat.add_le_add (hfg x.outcome) ih

/-- I3, separation half: the scored cadence never exceeds the issuance
    streak — scoring is a sub-count of receipts, never an independent
    number a producer can assert. -/
theorem scoredCadence_le_receiptStreak (l : List DayRecord) :
    scoredCadence l ≤ receiptStreak l :=
  countWith_le scoreVal receiptVal
    (fun o => by cases o <;> simp [scoreVal, receiptVal]) l

/-- I3, gating half (no-call): appending a no-call day leaves the
    scored cadence exactly unchanged and advances the streak by one.
    This is the Nov 1 / Nov 2 ruling, as arithmetic. -/
theorem noCall_keeps_cadence {reason : NoCallReason} (l : List DayRecord)
    (r : DayRecord) (hr : r.outcome = Outcome.noCall reason) :
    scoredCadence (l ++ [r]) = scoredCadence l ∧
    receiptStreak (l ++ [r]) = receiptStreak l + 1 := by
  rw [scoredCadence_step, receiptStreak_step, hr]
  simp [scoreVal, receiptVal]

/-- I3, gating half (missed): a missed day moves NEITHER ledger. -/
theorem missed_keeps_both (l : List DayRecord) (r : DayRecord)
    (hr : r.outcome = Outcome.missed) :
    scoredCadence (l ++ [r]) = scoredCadence l ∧
    receiptStreak (l ++ [r]) = receiptStreak l := by
  rw [scoredCadence_step, receiptStreak_step, hr]
  simp [scoreVal, receiptVal]

/-- I3, gating half (scored): a scored day advances both by exactly
    one — and by the step discipline it can only be appended when it
    carries a fresh, verified, canonical receipt (`StepOK`). -/
theorem scored_advances_both {c : Nat} (l : List DayRecord) (r : DayRecord)
    (hr : r.outcome = Outcome.scored c) :
    scoredCadence (l ++ [r]) = scoredCadence l + 1 ∧
    receiptStreak (l ++ [r]) = receiptStreak l + 1 := by
  rw [scoredCadence_step, receiptStreak_step, hr]
  simp [scoreVal, receiptVal]

/-! ## The consecutive run (the S7 gate's "14 consecutive") -/

/-- Leading scored run of a list. -/
def leadRun : List DayRecord → Nat
  | [] => 0
  | r :: t => if scoreVal r.outcome = 1 then leadRun t + 1 else 0

/-- The trailing run of consecutive scored days — the quantity the
    S7 gate's "14 consecutive daily briefs" speaks about. Distinct
    from `scoredCadence` (a pure count): a no-call or missed day
    resets the run to zero but does not reduce the count. SPEC.md
    records both readings; the tracker rule ("no-calls do not advance
    the scored cadence") is a statement about the count. -/
def scoredRun (l : List DayRecord) : Nat := leadRun l.reverse

theorem scoredRun_step (l : List DayRecord) (r : DayRecord) :
    scoredRun (l ++ [r]) =
      if scoreVal r.outcome = 1 then scoredRun l + 1 else 0 := by
  unfold scoredRun
  rw [List.reverse_append]
  have hrev : List.reverse [r] = [r] := rfl
  rw [hrev]
  show leadRun (r :: l.reverse) = _
  simp only [leadRun]

/-! ## The Nov 1–3, 2026 ledger, as a checked example

Epoch: day 0 = 2026-10-25, so the first slot is day 7 (Nov 1).
Input stamps: Oct 28 = day 3, Oct 31 = day 6.
Issue times (minutes): Nov 1 07:00 slot = 10500, actual 11:15 → 10755
(issued late, stamped with the TRUE time); Nov 2 07:00 → 11940;
Nov 3 07:00 → 13380. Hashes/ids are abstract stand-ins (100 = the
canonical repo artifact, 7 = the pinned cadence environment,
55 = the frozen S3c stress definition). -/

def cfg0 : Config := { canonicalHash := 100, envId := 7, freshBound := 2, firstDay := 7 }

/-- Nov 1: no-call receipt (stale_load) from the late directed run.
    Inputs latest Oct 28 (day 3): 7 ≤ 3 + 2 fails — stale, correctly
    not scored. Availability unverified. -/
def nov1 : DayRecord :=
  { day := 7, outcome := .noCall .staleLoad, artifactHash := 100, envId := 7,
    defHash := 55, inputStamp := some 3, issuedAt := 10755, availVerified := false }

/-- Nov 2: no-call receipt (stale_load). Inputs latest Oct 31 (day 6):
    within the D-2 bound, but availability unverified — either way the
    day cannot be scored in this model. -/
def nov2 : DayRecord :=
  { day := 8, outcome := .noCall .staleLoad, artifactHash := 100, envId := 7,
    defHash := 55, inputStamp := some 6, issuedAt := 11940, availVerified := false }

/-- Nov 3: the 07:00 run died (cross-environment duckdb failure) and
    wrote no receipt; the day resolves as missed. -/
def nov3 : DayRecord :=
  { day := 9, outcome := .missed, artifactHash := 100, envId := 7,
    defHash := 55, inputStamp := none, issuedAt := 13380, availVerified := false }

def novLedger : List DayRecord := [nov1, nov2, nov3]

/-- The three days form a reachable ledger under the step discipline. -/
example : Reachable cfg0 novLedger := by
  have s1 : StepOK cfg0 [] nov1 :=
    ⟨rfl, by decide,
      (⟨rfl, rfl⟩ :
        nov1.artifactHash = cfg0.canonicalHash ∧ nov1.envId = cfg0.envId)⟩
  have s2 : StepOK cfg0 [nov1] nov2 :=
    ⟨rfl, by decide,
      (⟨rfl, rfl⟩ :
        nov2.artifactHash = cfg0.canonicalHash ∧ nov2.envId = cfg0.envId)⟩
  have s3 : StepOK cfg0 [nov1, nov2] nov3 :=
    ⟨rfl, by decide, True.intro⟩
  exact Reachable.step (Reachable.step (Reachable.step Reachable.init s1) s2) s3

/-- The ruling, computed: issuance streak 2 (Nov 3 missed, not a
    receipt), scored cadence 0, consecutive scored run 0. -/
example : scoredCadence novLedger = 0 ∧ receiptStreak novLedger = 2 ∧
    scoredRun novLedger = 0 := by decide

/-- Nov 1's lateness is derived from the record itself. -/
example : IsLate nov1 := by
  show scheduled nov1.day < nov1.issuedAt; decide

/-- Refusal: a scored record wearing Nov 2's numbers (stamp day 6,
    target day 9 — outside the D-2 bound) is NOT a legal step, even
    with the canonical hash, the pinned env, and availability marked
    verified. Freshness is arithmetic, not assertion. -/
def scoredBad : DayRecord :=
  { day := 9, outcome := .scored 1, artifactHash := 100, envId := 7,
    defHash := 55, inputStamp := some 6, issuedAt := 13380, availVerified := true }

example : ¬ StepOK cfg0 [nov1, nov2] scoredBad := by
  intro h
  obtain ⟨-, -, hout⟩ := h
  have h2 : scoredBad.artifactHash = cfg0.canonicalHash ∧
      scoredBad.envId = cfg0.envId ∧ scoredBad.availVerified = true ∧
      ∃ s, scoredBad.inputStamp = some s ∧ s < scoredBad.day ∧
        scoredBad.day ≤ s + cfg0.freshBound := hout
  obtain ⟨-, -, -, s, hs, -, hle⟩ := h2
  have hs' : some 6 = some s := hs
  have hs6 : 6 = s := Option.some.inj hs'
  rw [← hs6] at hle
  exact absurd hle (by decide)

/-! ## Axiom audit (output recorded in BUILD-LOG.txt and SPEC.md) -/

#print axioms record_props
#print axioms receipt_hash_env
#print axioms scored_fresh
#print axioms never_early
#print axioms day_bounds
#print axioms pairwise_days
#print axioms day_unique
#print axioms day_surjective
#print axioms lookupDay_append
#print axioms lookupDay_spec
#print axioms lookup_of_mem_unique
#print axioms extends_prefix
#print axioms lookupDay_persistent
#print axioms lookupDay_complete
#print axioms no_backfill
#print axioms countWith_step
#print axioms scoredCadence_le_receiptStreak
#print axioms noCall_keeps_cadence
#print axioms missed_keeps_both
#print axioms scored_advances_both
#print axioms scoredRun_step
