# California Value Binary Geo

- recipe_name: california_value_binary_geo
- task_type: binary_classification
- source_dataset: sklearn.fetch_california_housing
- target_column: HighValue
- row_count: 4096
- column_count: 9
- csv_path: /home/lebedeffson/Code/neurofuzzy_analysis/experiments/datasets/california_value_binary_geo/dataset.csv

## Description

Balanced spatially informed binary classification benchmark derived from California Housing by thresholding median house value and preserving latitude/longitude as explicit geo-features.

## Feature Columns

- MedInc
- HouseAge
- AveRooms
- AveBedrms
- Population
- AveOccup
- Latitude
- Longitude

## Sampling

- kind: balanced_threshold_subsample
- sample_size: 4096
- original_row_count: 20640
- threshold: 1.797
- random_state: 42

## Task Notes

- problem_type: binary_classification
- positive_class_label: 1
- positive_class_meaning: original MedHouseVal >= 1.797000
- negative_class_meaning: original MedHouseVal < 1.797000
- geo_features: ['Latitude', 'Longitude']