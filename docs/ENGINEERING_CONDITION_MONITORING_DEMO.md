# Safe engineering condition-monitoring demonstration

The Product V1 demonstration concerns equipment health only. It has no targeting, weapon engagement, autonomous actuator, or control-command function.

1. Import telemetry such as temperature, torque and vibration with a binary maintenance-risk target; confirm the DatasetContract.
2. Train a probabilistic model, save validation evidence, calibrate when appropriate, and select both a class threshold and a separate ACCEPT/REVIEW confidence cutoff on validation only.
3. Declare the supported operating regime in a GeneralizationContract. A case outside that scope is explicitly `BLOCK` or `REVIEW`, never silently automated.
4. Inspect exact FIS/Decision-Tree evidence where available, or explicitly labelled post-hoc evidence and its checks.
5. Use `ACCEPT` only for in-scope cases above the review cutoff. Route low-confidence cases to `REVIEW`; mark unsupported cases `OUT-OF-SCOPE`.
6. Build the AssuranceCase and inspection-first VerificationBundle for audit.

The output supports maintenance triage by a human engineer. It does not issue an actuator command.
