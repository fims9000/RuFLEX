# Backward compatibility

V1.0/V1.1 persisted runs remain readable without a silent rewrite. Legacy
concrete kinds resolve at read time to compatible built-in identities when they
exist. A removed or unavailable adapter leaves the project and run inspectable;
only replay-capability negotiation becomes `UNAVAILABLE_RUNTIME`.

New `TrainingRun` schema v3 records adapter identity and runtime snapshot hash.
New explanation/check records carry explainer/validator identity. New study jobs
also carry a canonical local-backend identity while legacy `LOCAL` remains
readable.
