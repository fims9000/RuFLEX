# Covertype Binary Geo

- recipe_name: covtype_binary_geo
- task_type: binary_classification
- source_dataset: sklearn.fetch_covtype
- target_column: CoverTypeBinary
- row_count: 6000
- column_count: 11
- csv_path: /home/lebedeffson/Code/neurofuzzy_analysis/experiments/datasets/covtype_binary_geo/dataset.csv

## Description

Binary cartographic classification benchmark derived from the Forest CoverType dataset using the original continuous geo-features and a balanced class-1 vs class-2 subset.

## Feature Columns

- Elevation
- Aspect
- Slope
- Horizontal_Distance_To_Hydrology
- Vertical_Distance_To_Hydrology
- Horizontal_Distance_To_Roadways
- Hillshade_9am
- Hillshade_Noon
- Hillshade_3pm
- Horizontal_Distance_To_Fire_Points

## Sampling

- kind: balanced_binary_subsample
- sample_size: 6000
- max_balanced_sample_size: 423680
- original_row_count: 581012
- eligible_binary_row_count: 495141
- random_state: 42

## Task Notes

- problem_type: binary_classification
- positive_class_label: 1
- positive_class_meaning: original Cover_Type == 2
- negative_class_meaning: original Cover_Type == 1