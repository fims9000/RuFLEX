# Article Assets

Сюда имеет смысл складывать финальные материалы для статьи.

Сейчас автоматически генерируются такие артефакты:

- `results_table.csv`
- `results_table.md`
- `results_overview.png`
- `best_training_history.png`
- `membership_<variable>.png`
- `best_sample_top_rules.png`
- `best_sample_hidden_concepts.png`
- `best_sample_decision_concepts.png`
- `best_sample_fuzzification.png`
- `best_sample_concept_flow.txt`
- `best_sample_rule_chain.txt`
- `article_board_regression.png`
- `article_board_classification.png`

Дополнительно сюда можно складывать вручную подготовленные рисунки:

- `architecture_overview.png`
- `platform_layers.png`
- `dashboard_sample.png`
- `concept_flow_sample.png`
- `rule_chain_sample.png`
- `workbench_data_tab.png`
- `workbench_rules_tab.png`
- `workbench_explainability_tab.png`
- `ablation_table.csv`

Рекомендуемый принцип:

- сюда попадают только финальные или почти финальные артефакты для текста статьи;
- сырой экспериментальный вывод хранится в `experiments/`;
- в саму статью вставляются версии из этой папки, чтобы не терять контроль над финальным набором рисунков и таблиц.
