# Russian Studio presentation — current checkpoint

RuFLEX Studio now defaults to Russian. The project entry, compact navigation, Data route, and primary actions in Model, Training, Analysis and Evidence use shorter Russian labels. Common status badges are translated for display, while their persisted codes remain unchanged. Scientific object IDs, API contracts, persisted notes, thresholds and final-test rules were not changed. English remains available for the existing browser regression suite via `VITE_RUFLEX_UI_LANG=en`.

The 920 px Russian browser route creates a project, opens Data, Model and Training, then reaches Evidence. It checks visible Russian controls and a screenshot. The English compact visual baselines were refreshed after the HTML language default changed; the layout remains reachable at 920 and 640 px.

Checks: 126 Vitest tests in 14 files plus one API-client test; TypeScript/Vite build; 18/18 project-lifecycle E2E; Russian Studio E2E 1/1; English compact Studio E2E 1/1; `git diff --check`.

This is a presentation checkpoint, not full localization. Some deep engineering forms, backend-origin errors, persisted scientific notes and technical enum values still appear in English. Their translation must stay in the UI layer so persisted evidence and scientific provenance remain exact. No research result or model behavior changed.
