# Decisions

## D01 — observable scope

Only violations represented by declared project/evidence/provenance state are
primary candidates. Arbitrary semantic leakage from opaque values is not
claimed detectable.

## D02 — superseded pre-freeze audit

Protocol `69b2fe941450de3c6798d53ba563ac4b7dd59c3be63574e9747b54efa8162f02`
and manifest `bc466c520fd565d03e069ad602c2c5ec3ec6f6fd2402714c51572305483c8499`
are `SUPERSEDED_BEFORE_TEST_UNLOCK`: pre-freeze scientific audit found a shadow
detector and incomplete executable lock. Locked suite accessed: NO.

## D03 — superseded native-adapter pre-freeze revision

Protocol `fae85459726afc5ab94714ea80a5c0cf6b473ee6494b1b02969bcf5d0c3062ab`
and manifest `6bf4ac4d9c37ccd2399b4465cbf8d778451bb34faaedd5e92f186d25bdf56272`
are `SUPERSEDED_PRE_UNLOCK`. The executor then refused correctly but did not
contain its post-authorization 60-pair execution path or frozen execution
contracts. This revision adds native service-bound contracts, a resumable
executor and dry-plan validation without changing Product V1.0.1. Locked suite
accessed: NO.

## D04 — superseded pre-unlock execution binding and authorization defect

Protocol `c0389f06aa35923b6d1861ab535a45aa1f87ad071c85ad35b78be664e8b66b6d`,
manifest `7a8183cc816f1ffb4598d891309adb0e60d4051ff552e51f9a09d41796560001`,
and plan `0bf9e2469d6bd0c786be2e0fb4c1dcab379239554e28adb5356b23c39ba3fb7d`
are `SUPERSEDED_BEFORE_TEST_UNLOCK` for
`PRE_UNLOCK_EXECUTION_BINDING_AND_AUTHORIZATION_DEFECT`. The adapter had not
consumed the frozen materialized generator input, and authorization would have
mutated the frozen manifest. Locked outcomes executed: NO.
