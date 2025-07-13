import shap
import matplotlib.pyplot as plt
import numpy as np

def explain_shap(model, scaler, X, sample_size=100, feature_names=None):
    # Предобработка
    if 'Unnamed: 0' in X.columns:
        X = X.drop(columns=['Unnamed: 0'])
    X = X.select_dtypes(include=[np.number])
    X_s = scaler.transform(X)
    X_sample = X_s[:sample_size] if sample_size and X_s.shape[0] > sample_size else X_s

    def predict_fn(data):
        preds = model.predict(data)
        return np.array(preds).reshape(-1)

    explainer = shap.KernelExplainer(predict_fn, X_sample)
    shap_values = explainer.shap_values(X_sample)

    # 1. Summary Plot (dot)
    shap.summary_plot(shap_values, X_sample, feature_names=feature_names)
    plt.show()

    # 2. Bar Plot
    shap.summary_plot(shap_values, X_sample, feature_names=feature_names, plot_type="bar")
    plt.show()

    # 3. Force Plot (для первого примера)
    shap.initjs()
    shap.force_plot(explainer.expected_value, shap_values[0], X_sample[0], feature_names=feature_names, matplotlib=True)
    plt.show()

    # 4. Waterfall Plot (для первого примера)
    shap.plots.waterfall(shap.Explanation(values=shap_values[0],
                                          base_values=explainer.expected_value,
                                          data=X_sample[0],
                                          feature_names=feature_names))
    plt.show()

    # 5. Decision Plot (для всех примеров)
    shap.decision_plot(explainer.expected_value, shap_values, X_sample, feature_names=feature_names)
    plt.show()

