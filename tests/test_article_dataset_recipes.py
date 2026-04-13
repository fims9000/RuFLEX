from ruflex.experiments.article_datasets import list_article_dataset_recipes


def test_default_article_dataset_recipes_are_article_grade() -> None:
    recipes = list_article_dataset_recipes()
    recipe_map = {item["name"]: item for item in recipes}

    assert "california_housing_regression" in recipe_map
    assert "california_value_binary_geo" in recipe_map
    assert "covtype_binary_geo" in recipe_map

    default_names = {item["name"] for item in recipes if item["default_enabled"]}
    assert default_names == {
        "california_housing_regression",
        "california_value_binary_geo",
        "covtype_binary_geo",
    }
    assert recipe_map["covtype_binary_geo"]["default_enabled"] is True
