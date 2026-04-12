from __future__ import annotations

import numpy as np
import pandas as pd

from ruflex.explain.explainer import Explainer
from ruflex.training.config import ModelTrainingConfig
from ruflex.visualization.plots import Visualizer


class Trainer:
    def fit(self, project, training_config: ModelTrainingConfig | None = None):
        return project.train(training_config=training_config)


class Evaluator:
    def evaluate(self, project, features: pd.DataFrame | np.ndarray, targets: np.ndarray) -> dict[str, float]:
        predictions = project.predict(features)
        return project._compute_metrics(np.asarray(targets, dtype=float), predictions)

    def explain(self, project, features: pd.DataFrame | np.ndarray, top_k_rules: int = 2, as_text: bool = False):
        return project.explain(features, top_k_rules=top_k_rules, as_text=as_text)

    def dashboard(self, project, features: pd.DataFrame | np.ndarray, top_k_rules: int = 2):
        return project.dashboard(features, top_k_rules=top_k_rules)

    def model_report(self, project, decimals: int = 3) -> str:
        return project.model_report(decimals=decimals)

    def concept_flow(self, project, features: pd.DataFrame | np.ndarray, top_k_rules: int = 2, as_text: bool = False):
        return project.concept_flow(features, top_k_rules=top_k_rules, as_text=as_text)

    def path_concept_flow(
        self,
        project,
        features: pd.DataFrame | np.ndarray,
        top_k_rules: int = 2,
        as_text: bool = False,
    ):
        return project.path_concept_flow(features, top_k_rules=top_k_rules, as_text=as_text)

    def rule_chain_flow(
        self,
        project,
        features: pd.DataFrame | np.ndarray,
        top_k_rules: int = 2,
        as_text: bool = False,
    ):
        return project.rule_chain_flow(features, top_k_rules=top_k_rules, as_text=as_text)

    def explainer(self) -> Explainer:
        return Explainer()

    def visualizer(self) -> Visualizer:
        return Visualizer()
