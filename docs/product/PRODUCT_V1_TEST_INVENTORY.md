# RuFLEX Product V1 test inventory

This inventory describes current implementation coverage, not a claim that a green test is a universal scientific guarantee.

| Category / file | Main capability | Reopen | Negative/invariant |
|---|---|---:|---|
| Python `test_dataset_contract.py`, `test_product_route.py` | CSV/XLSX contracts, audit, persisted artifacts | yes | schema/contract validation; train-only protocol |
| Python `test_fis_designer_domain.py`, `test_fis_interop.py` | FIS variables/MFs/rules, trace, `.fis` interchange | yes | semantic compatibility is explicit |
| Python `test_training_product_route.py`, `test_training_route.py`, `test_model_catalog.py` | ANFIS, baselines, tree/ensemble artifacts | yes | preprocessing fit on TRAIN; final test firewall |
| Python `test_evidence_product_route.py` | exact tree/FIS and compatible post-hoc XAI/checks | yes | no ensemble constituent relabelled exact |
| Python `test_generalization_contract_product_route.py`, `test_slice_lab_product_route.py` | scope contract and slices | yes | undeclared/invalid scope is not accepted |
| Python `test_lineage_product_route.py` | provenance graph including FIS→BehaviorSpec→result | yes | only saved references form edges |
| Python `test_expert_correction_product_route.py` | train-only Sugeno correction | yes | locked final test not used |
| Python `test_final_test_product_route.py` | frozen validation policy / final test | yes | retuning after unlock blocked |
| Browser `product-golden-route.spec.ts` | data→FIS→trace→reopen | yes | persisted Studio route |
| Browser `training-evaluate.spec.ts`, `multiseed-study-reopen.spec.ts` | real training, evaluation, Study | yes | locked test not selected |
| Browser `analysis-calibration-threshold.spec.ts` | calibration, threshold, selective policy, demo | yes | validation-only policy |
| Browser `evidence-occlusion.spec.ts`, `explanation-reproducibility.spec.ts` | post-hoc XAI/checks, cross-run agreement, BehaviorSpecs | yes | attribution not causal; agreements separate |
| Browser `exhaustive-lab.spec.ts`, `assurance-case.spec.ts` | exact finite enumeration, AssuranceCase, bundle | yes | no trust score; finite exactness label |
| Browser `project-lifecycle.spec.ts` | create/save/close/open/read-only/offline | yes | read-only and future schema errors |
| Browser `visual-foundation.spec.ts` | light/dark visual baselines | n/a | controlled offline state |
| Browser `product-evidence-capture.spec.ts` | reproducible 19-screen Product V1 evidence route | yes | fails when a required state is unreachable |

Frontend unit coverage is `frontend/tests/api-client.test.mjs`. Upstream/backend compatibility coverage is under `tests/upstream/`; it protects the embedded backend foundations but is not a substitute for Product V1 user-route evidence.
