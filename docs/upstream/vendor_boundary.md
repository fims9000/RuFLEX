# Deep Fuzzy Boundary

В `RuFLEX` нужно считать источником deep fuzzy-логики именно репозиторий
`deep-neuro-fuzzy`.

## Что берем оттуда как vendored snapshot

Эти части должны обновляться из upstream-репозитория, а не переписываться локально вручную:

- `src/ruanfis/`
- `tests/upstream/`
- `examples/upstream/`
- `docs/upstream/deep_fuzzy_feature_learning.md`
- upstream metadata в `docs/upstream/vendor_manifest.json`

Именно здесь живет deep fuzzy backend:

- fuzzy blocks;
- hierarchical builders;
- bootstrap/stage-wise pretraining;
- refinement loop;
- explainability trace logic;
- backend serialization;
- backend benchmark helpers.

## Что остается нашим слоем RuFLEX

Это уже не upstream deep fuzzy, а собственная платформа:

- `src/ruflex/core/`
- `src/ruflex/data/`
- `src/ruflex/models/` как адаптеры и платформенные спецификации;
- `src/ruflex/training/` как platform-level config layer;
- `src/ruflex/sdk/`
- `src/ruflex/io/`
- `src/ruflex/visualization/`
- `src/ruflex/ui/`
- наши прикладные examples и tests вне `upstream/`.

## Правило изменения кода

Если меняется deep fuzzy backend, сначала меняем upstream-репозиторий
`deep-neuro-fuzzy`, а потом обновляем vendored snapshot в `RuFLEX`.

Если меняется платформенный API, UX, проектная структура, data flow,
экспорт проектов или UI, меняем `src/ruflex`.

