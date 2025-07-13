import shap
import matplotlib.pyplot as plt
import numpy as np

def explain_shap(model, scaler, X, sample_size=100, feature_names=None):
    # Удаляем лишние столбцы, если есть
    if 'Unnamed: 0' in X.columns:
        X = X.drop(columns=['Unnamed: 0'])
    X = X.select_dtypes(include=[np.number])
    X_s = scaler.transform(X)

    # Сэмплируем для ускорения
    if sample_size and X_s.shape[0] > sample_size:
        X_sample = X_s[:sample_size]
    else:
        X_sample = X_s

    # Гарантируем двумерность X_sample
    if len(X_sample.shape) == 1:
        X_sample = X_sample.reshape(1, -1)

    # Обёртка для корректной работы с SHAP
    def predict_fn(data):
        preds = model.predict(data)
        return np.array(preds).reshape(-1)

    explainer = shap.KernelExplainer(predict_fn, X_sample)
    shap_values = explainer.shap_values(X_sample)

    # 1. Summary plot
    shap.summary_plot(shap_values, X_sample, feature_names=feature_names)
    plt.show()

    # 2. Bar plot важности
    shap.summary_plot(shap_values, X_sample, feature_names=feature_names, plot_type="bar")
    plt.show()

    # 3. Force plot для первого примера
    shap.initjs()
    shap.force_plot(explainer.expected_value, shap_values[0], X_sample[0], feature_names=feature_names, matplotlib=True)
    plt.show()

