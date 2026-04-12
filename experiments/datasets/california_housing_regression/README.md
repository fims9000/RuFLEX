# California Housing Regression

- recipe_name: california_housing_regression
- task_type: regression
- source_dataset: sklearn.fetch_california_housing
- target_column: MedHouseVal
- row_count: 4096
- column_count: 9
- csv_path: /home/lebedeffson/Code/neurofuzzy_analysis/experiments/datasets/california_housing_regression/dataset.csv

## Description

Geo-oriented tabular regression benchmark based on California Housing with latitude and longitude preserved as explicit spatial predictors.

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

- kind: random_subsample
- sample_size: 4096
- original_row_count: 20640
- random_state: 42

## Task Notes

- problem_type: regression
- geo_features: ['Latitude', 'Longitude']