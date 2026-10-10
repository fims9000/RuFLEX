# Alpha categorical evidence input checkpoint

Studio's Evidence Workbench now obtains categorical choices from the selected
TrainingRun's persisted TRAIN-fitted `OrdinalEncoder`. It submits the frozen
numeric code to the existing product-native explanation API, without fitting a
new encoder or changing any persisted explanation schema. A missing, unreadable,
or run/dataset-incompatible transform pauses explanation generation and offers
an explicit retry. Numeric-only runs retain their existing input path.

Verification: 50 focused frontend unit tests passed; TypeScript/Vite production
build passed; the synthetic categorical tree browser route trained, traced,
generated an explanation with the frozen code, and verified the Evidence route
after closing and reopening the project (1/1). `git diff --check` passed for
the changed source and test files. No frozen research artifact was modified.

Remaining scope: other run-bound inputs in the Evidence Workbench, including
pairwise BehaviorSpec comparison and the telemetry demonstration, still expose
numeric model coordinates; this checkpoint does not claim a complete
raw-category input experience across every Studio action.
