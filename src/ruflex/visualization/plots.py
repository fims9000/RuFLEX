from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from ruflex.core.variables import VariableSpec
from ruflex.models.base import TrainingSummary


def plot_membership_functions(variable: VariableSpec, points: int = 200):
    if variable.value_range is None:
        raise ValueError("Variable value_range is required for plotting membership functions.")
    x_axis = np.linspace(variable.value_range[0], variable.value_range[1], points)
    values = variable.membership.evaluate(x_axis)
    figure, axis = plt.subplots(figsize=(9, 5))
    for index, term_name in enumerate(variable.term_names):
        axis.plot(x_axis, values[:, index], label=term_name)
    axis.set_title(f"Функции принадлежности: {variable.name}", fontsize=16)
    axis.set_xlabel(variable.name, fontsize=13)
    axis.set_ylabel("Степень принадлежности", fontsize=13)
    axis.tick_params(axis="both", labelsize=11)
    axis.legend(fontsize=11)
    return figure


def plot_training_history(summary: TrainingSummary):
    figure, axis = plt.subplots(figsize=(9, 5))
    epochs = [entry.epoch for entry in summary.history]
    axis.plot(epochs, [entry.train_loss for entry in summary.history], label="Обучающая выборка")
    validation = [entry.validation_loss for entry in summary.history if entry.validation_loss is not None]
    if validation:
        axis.plot(epochs[: len(validation)], validation, label="Проверочная выборка")
    axis.set_title("История обучения", fontsize=16)
    axis.set_xlabel("Эпоха", fontsize=13)
    axis.set_ylabel("Функция потерь", fontsize=13)
    axis.tick_params(axis="both", labelsize=11)
    axis.legend(fontsize=11)
    return figure


class Visualizer:
    def membership_functions(self, variable: VariableSpec, points: int = 200):
        return plot_membership_functions(variable, points=points)

    def training_history(self, summary: TrainingSummary):
        return plot_training_history(summary)
