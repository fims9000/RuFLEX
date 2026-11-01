# Quiet project overview

The project landing page now prioritizes the next action and five workbench entry points. A passing integrity report remains available under Properties but no longer occupies the main canvas. A failed or unavailable check remains visible with its exact issue and retry action. Empty lineage is hidden; persisted object relationships still appear once present, and a lineage read error still offers retry.

The redundant overview heading and idle footer counters were removed. The footer retains the current operation status and shows a problem count only when there is an error. No integrity, lineage, persistence, policy or final-test check was removed from the product logic.

Verification: TypeScript/Vite build; 126 frontend unit tests plus one API-client test; 20 project-lifecycle/compact browser tests, including failed-integrity visibility; Russian 920 px project route; light/dark visual routes. Screenshots were refreshed after inspecting the changed layout. Existing unrelated `docs/article/` edits were not touched.
