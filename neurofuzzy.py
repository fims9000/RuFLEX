# В самом верху файла neurofuzzy.py
from xanfis.models.base_anfis import CustomANFIS

# Патчим CustomANFIS: создаём публичный метод __get_strength_by_prod
if hasattr(CustomANFIS, "_CustomANFIS__get_strength_by_prod"):
    CustomANFIS.__get_strength_by_prod = CustomANFIS._CustomANFIS__get_strength_by_prod

import os
import pickle
import joblib
import numpy as np
import torch
from xanfis import GdAnfisRegressor,GdAnfisClassifier
from xanfis.models.base_anfis import BaseAnfis
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def run_neurofuzzy_analysis(
    dataset, task_type, num_rules, mf_type, epochs, batch_size, lr,n_patience,optim_var
):
    # Предобработка данных с заменой пропусков
    X = dataset.iloc[:, :-1].copy()
    if 'Unnamed: 0' in X.columns:
        X.drop(columns=['Unnamed: 0'], inplace=True)
    X = X.select_dtypes(include=[np.number])
    # Удаление пропусков
    X = X.dropna()
    y = dataset.iloc[:, -1].loc[X.index].values.flatten()


    # Разбиение
    strat = y if task_type == "Классификация" else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=strat
    )

    # Масштабирование
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    # Параметры модели
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    params = dict(num_rules=num_rules, mf_class=mf_type,
                  reg_lambda=0.001, device=device, optim=optim_var,
                  epochs=epochs,batch_size=batch_size,early_stopping=True,
                  n_patience=n_patience,valid_rate=0.1,verbose=True,epsilon=1e-4)
    probas=None
    # Обучение
    if task_type == "Классификация":
        model = GdAnfisClassifier(**params)
        model.fit(X_train_s, y_train, optim_params={'lr': lr})

    else:
        model = GdAnfisRegressor(**params)
        model.fit(X_train_s, y_train,
                  optim_params={'lr': lr}, grad_clip=0.9)

    # Предсказание
    y_pred = np.asarray(model.predict(X_test_s)).ravel()

    return {
        "model": model,
        "scaler": scaler,
        "X_train": X_train, "y_train": y_train,
        "X_test": X_test, "y_test": y_test,
        "y_pred": y_pred,
    }

def save_full_model(model, scaler, filepath_base):
    """
    Сохраняет:
      {filepath_base}_anfis.pkl  — модель
      {filepath_base}_scaler.gz  — scaler
    """
    os.makedirs(os.path.dirname(filepath_base), exist_ok=True)
    # 1) ANFIS-модель
    model.save_model(save_path=os.path.dirname(filepath_base),
                     filename=os.path.basename(filepath_base) + "_anfis.pkl")
    # 2) scaler
    joblib.dump(scaler, filepath_base + "_scaler.gz")

def load_full_model(model_path):
    """
    Загружает модель и scaler по пути к файлу модели:
      model_path = ".../my_model_anfis.pkl"
    """
    folder, name = os.path.split(model_path)
    base = name[:-10]  # убираем "_anfis.pkl"
    # 1) Загружаем ANFIS
    model: BaseAnfis = BaseAnfis.load_model(load_path=folder, filename=name)
    # 2) Загружаем scaler
    scaler = joblib.load(os.path.join(folder, base + "_scaler.gz"))
    return model, scaler

def predict_with_model(model, scaler, dataset):
    X = dataset.iloc[:, :-1].copy()
    if 'Unnamed: 0' in X.columns:
        X.drop(columns=['Unnamed: 0'], inplace=True)
    X = X.select_dtypes(include=[np.number])  # Не .values!
    X_s = scaler.transform(X)  # Теперь X — DataFrame с именами столбцов
    model.network.eval()
    with torch.no_grad():
        y_pred = np.asarray(model.predict(X_s)).ravel()
    y_test = dataset.iloc[:, -1].values if dataset.shape[1] > 1 else None
    return y_pred, y_test


def extract_human_rules(model, X, y, dataset, model_params=None):
    rules = ""
    if model_params:
        rules += "Параметры модели:\n"
        for k, v in model_params.items():
            rules += f"- {k}: {v}\n"
        rules += "\n"
    rules += "Человекочитаемые правила нейронечёткой системы:\n"
    try:
        coeffs = model.network.state_dict()['coeffs'].detach().cpu().numpy()
        num_rules = coeffs.shape[0]
        num_features = coeffs.shape[1] - 1
        feature_names = [c for c in dataset.columns if c != 'Unnamed: 0'][:-1]
        key_rules = []
        for i in range(num_rules):
            rule_coeffs = coeffs[i, :, 0]
            if np.max(np.abs(rule_coeffs)) > 0.1:
                key_rules.append(i)
        for i in key_rules:
            rule_coeffs = coeffs[i, :, 0]
            rules += f"\nПравило {i+1}\nКоэффициенты:\n"
            for j in range(num_features):
                rules += f"- {feature_names[j]}: {rule_coeffs[j]:.4f}\n"
            rules += f"- Смещение (bias): {rule_coeffs[-1]:.4f}\n"
            increasing = [feature_names[j] for j in range(num_features) if rule_coeffs[j] > 0.1]
            decreasing = [feature_names[j] for j in range(num_features) if rule_coeffs[j] < -0.1]
            direction = np.sum(rule_coeffs[:-1])
            if direction > 0:
                result = "выход увеличивается"
            elif direction < 0:
                result = "выход уменьшается"
            else:
                result = "выход существенно не меняется"
            rules += "\nЧеловекочитаемая интерпретация:\n"
            if increasing:
                rules += "Если большое значение: " + ", ".join(increasing) + ",\n"
            if decreasing:
                rules += "и маленькое значение: " + ", ".join(decreasing) + ",\n"
            if not increasing and not decreasing:
                rules += "Нет ярко выраженных влияющих признаков,\n"
            rules += f"то {result}.\n"
    except Exception as e:
        rules += f"\n(Не удалось извлечь коэффициенты правил: {e})\n"
    return rules
