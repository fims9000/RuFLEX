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
    figure, axis = plt.subplots(figsize=(8, 4))
    for index, term_name in enumerate(variable.term_names):
        axis.plot(x_axis, values[:, index], label=term_name)
    axis.set_title(f"Membership functions: {variable.name}")
    axis.set_xlabel(variable.name)
    axis.set_ylabel("membership")
    axis.legend()
    return figure


def plot_training_history(summary: TrainingSummary):
    figure, axis = plt.subplots(figsize=(8, 4))
    epochs = [entry.epoch for entry in summary.history]
    axis.plot(epochs, [entry.train_loss for entry in summary.history], label="train_loss")
    validation = [entry.validation_loss for entry in summary.history if entry.validation_loss is not None]
    if validation:
        axis.plot(epochs[: len(validation)], validation, label="validation_loss")
    axis.set_title("Training history")
    axis.set_xlabel("epoch")
    axis.set_ylabel("loss")
    axis.legend()
    return figure


class Visualizer:
    def membership_functions(self, variable: VariableSpec, points: int = 200):
        return plot_membership_functions(variable, points=points)

    def training_history(self, summary: TrainingSummary):
        return plot_training_history(summary)

