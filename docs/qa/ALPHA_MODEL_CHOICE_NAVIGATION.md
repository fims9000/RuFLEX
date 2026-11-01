# Alpha model-choice navigation

The Models section is the editable rule-based FIS workbench, not the selector for trainable estimator families. A compact guide now points to Training, where users select regression, trees, ensembles, MLP or the flat neuro-fuzzy model and configure the supported parameters. If no DatasetContract is saved, the guide points to Data instead. Creating a default FIS is unavailable until a confirmed dataset is loaded, so a new project no longer exposes a raw missing `dataset-contract.json` exception through that button. A failed dataset read remains a distinct error state; it is not treated as an empty project.

Reproduction: the user project `1` contained a `data/` directory but no `dataset-contract.json`. The earlier Models page permitted `Create FIS from dataset`, which reached the backend without the required contract. No existing project files or research evidence were changed.

Checks: TypeScript/Vite production build and 127 frontend unit tests passed. A Russian-language Playwright route created a new project, verified the absent FIS action and Data navigation, saved the 80-row synthetic practice DatasetContract, returned to Models, opened Training through the new button, and selected MLP among six available families. The adjacent Russian Studio route also passed (2/2). The practice dataset is only a UI fixture, not research evidence.
