LOCAL SELECTION MANIFESTS -- 20 October 2026

CURRENT EXECUTION STATUS (selection history below remains unchanged):
The user subsequently authorized the v3 primary list. All 16 events completed
two box conditions x four H/R groups = 128 main branches on the local RTX3080.
2967/BC01 remains UNRUN. No held-out evaluation or training has been performed.
The frozen review's historical approval field is not rewritten: authorization
is recorded in the separate local execution plan. See RECOVERY_COHORT_GUIDE.txt.

Authoritative split: ytvis2021-200-seed550-v1.json
Authoritative candidate queue: independent-candidates-20261020-v2.json
Authoritative event review: independent-events-review-20261020-v3.json
Manual scene specifications: independent-events-spec-20261020-v3.json
RGB duplicate screen: ytvis2021-duplicate-screen-v1.json

The split freezes 120 development / 40 validation / 40 evaluation video IDs,
plus 26 excluded IDs. All five original pilots stay in development. Exact or
strong sparse-frame duplicate groups stay together. Assignment uses audited
categories, lengths, old-pilot membership and a seeded coverage-constrained
MILP; it is NOT a uniform random sample of natural scene frequencies.

The 200 selected IDs represent 198 automatically screened visual groups, not
200 proven independent source recordings. Original URLs/timestamps are absent.
Sparse hashes miss some related clips: later obvious related clips must be
quarantined, not used to reshuffle held-out sets after seeing outcomes.

Queue v1 is SUPERSEDED, retained for audit only. Before any new baseline
inference, video 2884 was found to share a visual group with old cat pilot
2689. The v2 rule excludes whole old-pilot groups, not only old IDs. The split
was not rerolled. Queue v2 fixes 32 development candidates and six reserve IDs.

These JSON files authorize NO H/R runs. A later event-review manifest requires
human review and an explicit follow-up task before interventions are executed.
Validation/evaluation RGB are not rendered or inferred for event exploration;
the earlier data-only duplicate hash pass does not expose their predictions.

Event spec/review v1 is a retained draft. V2 keeps the same 16 events but adds
the GT-observability audit: E05 (2967 GT3 t14) has only 12 visible follow-up
steps, with the target out of view at the 20/30-step endpoints. It is a REVIEW
BOUNDARY case, not a complete long-window recovery example. All 16 meet input
and retained-state criteria, which is NOT the same as 16 fully observable
long-window events. See the Chinese offline review for this decision and the
other short visibility gaps. No H/R has been executed in either draft.

V3 implements the user's review: primary E05 is now 2705 / GT1 / step16
(kettlebell posture transition), with GT visible at EVERY step17..46. The
previous 2967 / GT3 / step14 remains BC01 in a separate boundary_cases list,
excluded from primary counts and complete-window delayed-recovery statistics.
The other 15 primary events, split and candidate queue are unchanged. E09 and
E13 still have their original brief visibility gaps; replacing E05 does NOT
mean that every primary video now has 30 continuously visible GT steps.
V1/V2 and their reports remain intact. V3 used existing cached baselines and
RGB/GT only: no new inference, H/R run, training, school access or publication.

Reproducible code map (all modules are tracking_lab):
  selection_split.fingerprint       raw RGB -> duplicate fingerprints/groups
  selection_split.freeze_split      audit/groups -> frozen 120/40/40 split
  selection_screen.choose_candidates split -> frozen development-only queue
  selection_screen.export_candidates queue -> fresh lossless RGB/GT exports
  selection_screen.screen           RGB/GT -> feature hints/contact sheets
  selection_baselines.execute       queue -> automatic A0/B0 ONLY, local3080
  selection_preflight.catalog       cached predictions -> read-only eligibility

An overview is not proof of occlusion, acceleration is not proof of a motion
mechanism, and a missing mask is not proof of model drift. Review RGB context,
GT continuity, locked prefix identity, retained state and YOLO availability.
All temporal values are zero-based EXPORTED STEPS, never seconds.

Preparation creates fresh output paths. Do not overwrite old baseline/H/R
archives, the frozen split, or completed per-video screening records.
No school server, H/R intervention, training, Git push or website publication
is part of this selection task.
