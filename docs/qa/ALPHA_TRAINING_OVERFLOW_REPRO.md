# Alpha Training workspace overflow reproduction

The focused synthetic-practice browser route at the supported minimum viewport
`1180 × 720` reproduces horizontal clipping after opening Studies. No research
dataset or saved project is involved.

Before the fix, the workspace measured 492 px wide while the Training config
panel extended to x=2242 (workspace right edge x=860). Browser-computed widths:
the outer `.feature-workspace` was 444 px, but its implicit grid column and
`.training-grid` were 1850 px. The nested three-column config grid inherited
600 px columns from the intrinsic width of controls with long option text.

Setting `min-width: 0` on the Training grid and its panel did not constrain the
parent's implicit auto-minimum track. Changing only the Training responsive
track from `1fr` to `minmax(0, 1fr)` also did not constrain that parent track.
The root correction is to give `.feature-workspace` an explicit zero-minimum
column, then verify that the panel and its controls fit the workspace. The
browser geometry assertion is retained as a regression gate.
