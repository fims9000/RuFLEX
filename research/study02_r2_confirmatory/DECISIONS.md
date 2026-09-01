# Decisions

## D01 — superseded pre-unlock freeze

Protocol `a5aaffc27e802617c543870721ec44ceff949c87a2fa3a920f84619fc7a2014d`,
manifest `d8881033031e6ce17049e18a284121b8f90eeeab647791a6750f7de331e9ffb9`,
and plan `42784bb9f34d1918af407a63342f0c286aaffdc06a45cbf1ee51e32a412c0368`
are `SUPERSEDED_BEFORE_TEST_UNLOCK`. Reason: execution did not verify every
frozen code hash at run time and result validation lacked exact scenario-to-
contract binding. Locked outcomes executed: NO.

## D02 — superseded final-validator freeze

Protocol `bbcb19adf4f4d1613d54ddfb0593a8d062fda37629df1b95299f42d923836918`,
manifest `7fd4a5883fd950e6a3270988552d1835b240d66568476b828313e7cea34c663b`,
and plan `c0ecc52380d5058fc62dfa40f8a20c41f883c10ba490589b1439e98aad63c2ab`
are `SUPERSEDED_BEFORE_TEST_UNLOCK` only to freeze strict row-set cardinality
and observed CLEAN/CORRUPT semantics before outcomes. Locked outcomes executed:
NO.
