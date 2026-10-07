# Alpha Study seed-provenance correction

This product correction applies only to newly submitted Studio work. It does
not rewrite persisted TrainingRuns, frozen research studies, policies, or
results.

The Studio exposed training and split seeds, but an individual run without a
saved SplitContract sent `split_seed: null`. The backend then used the fitting
seed for split membership. Studio now submits the displayed split seed
explicitly; a synthetic end-to-end route verifies distinct `42/7` split/fit
seeds in the request, persisted run, and reopened view.

A second route exposed a varying-split Study after a fixed SplitContract had
been saved. The backend already supports independent per-run random splits,
but Studio previously rejected this route and displayed all runs under the
same fixed training seed. Varying-split and combined Studies now omit the
unrelated fixed SplitContract binding, require the RANDOM split family, and
show both split and fitting seeds in the job and Explorer. They do not claim
case-level agreement across unmatched validation membership.

For equal validation metrics, fixed-training-seed runs previously tied again
on that same seed, leaving input order as an implicit selector. New Study
selection uses lowest training seed, then lowest split seed. Existing frozen
selected-run identities remain unchanged. This deterministic product rule is
regression-tested in both input orders; no A01/S03 research artifacts were
recomputed or reinterpreted.

The Studio seed inputs now retain invalid drafts instead of interpreting an
empty string as zero. Single-run training, split freeze, and Study submission
are disabled while their required seed is blank, fractional, negative, or
outside the common NumPy/scikit-learn 32-bit seed range. API request schemas
enforce the same `0..4294967295` bound before any project operation. Existing
persisted objects are not migrated.
