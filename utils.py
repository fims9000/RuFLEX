import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tkinter import messagebox, Toplevel
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from sklearn.metrics import (
    confusion_matrix,
    mean_squared_error,
    mean_absolute_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_curve,
    auc,
    precision_recall_curve
)
from tabulate import tabulate

def load_dataset(path: str) -> pd.DataFrame:
    """
    Загружает CSV или Excel файл в pandas.DataFrame.
    """
    ext = path.lower().split('.')[-1]
    if ext == 'csv':
        return pd.read_csv(path)
    if ext in ('xls', 'xlsx'):
        return pd.read_excel(path, engine='openpyxl')
    raise ValueError(f"Unsupported file format: {ext}")

def get_basic_stats(df: pd.DataFrame) -> str:
    """
    Возвращает строку с базовой статистикой DataFrame:
    количество строк, столбцов, типы признаков, описательную статистику
    и количество пропущенных значений по каждому столбцу.
    """
    cols = [c for c in df.columns if c != 'Unnamed: 0']
    info = f"📊 {len(df)} строк × {len(cols)} столбцов\n\n"
    info += "🗂️ Признаки и их типы:\n"
    for c in cols:
        info += f" • {c}: {df[c].dtype}\n"
    desc = df[cols].describe().loc[['mean', 'std', 'min', 'max']].T
    info += "\n📈 Статистика признаков (mean, std, min, max):\n"
    info += tabulate(desc, headers="keys", tablefmt="github", floatfmt=".3f")
    
    # Добавляем количество пропущенных значений
    missing_counts = df[cols].isnull().sum()
    info += "\n\n⚠️ Количество пропущенных значений по признакам:\n"
    for c in cols:
        info += f" • {c}: {missing_counts[c]}\n"
    
    target = cols[-1]
    info += f"\n\n🎯 Целевая переменная: '{target}' — {df[target].nunique()} уникальных значений"
    return info


def show_corr_matrix(df: pd.DataFrame, root):
    """
    Отображает корреляционную матрицу числовых признаков в отдельном окне Tkinter.
    """
    if df is None:
        messagebox.showwarning("Нет данных", "Пожалуйста, загрузите датасет")
        return
    num_df = df.select_dtypes(include=[np.number]).copy()
    if 'Unnamed: 0' in num_df.columns:
        num_df.drop(columns=['Unnamed: 0'], inplace=True)
    corr = num_df.corr()

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(corr, cmap='coolwarm')
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha='right')
    ax.set_yticks(range(len(corr.columns)))
    ax.set_yticklabels(corr.columns)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.iat[i, j]:.2f}",
                    ha='center', va='center',
                    color='white' if abs(corr.iat[i, j]) > 0.5 else 'black',
                    fontsize=8)
    fig.colorbar(im, ax=ax)
    ax.set_title('Корреляционная матрица')
    plt.tight_layout()

    win = Toplevel(root)
    win.title("Корреляционная матрица")
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.get_tk_widget().pack(fill='both', expand=True)
    canvas.draw()

def get_model_param_count(model):
    """
    Возвращает количество параметров в модели.
    """
    return sum(p.numel() for p in model.network.parameters())

def get_model_device(model):
    """
    Возвращает строку с устройством (CPU/GPU), на котором находится модель.
    """
    return str(next(model.network.parameters()).device)

def get_model_params_dict(model, task_type, dataset, num_rules, mf_class, epochs, batch_size, lr):
    """
    Возвращает словарь с основными параметрами модели.
    """
    return {
        "Тип задачи": task_type,
        "Число входных признаков": dataset.shape[1] - 1,
        "Число правил": int(num_rules),
        "Тип MF": mf_class,
        "Эпох обучения": int(epochs),
        "Размер батча": int(batch_size),
        "Learning rate": float(lr),
        "Параметров в модели": get_model_param_count(model),
        "Устройство": get_model_device(model)
    }

def visualize_results(app):
    """
    Строит выбранный график и отображает метрики на основе app.y_test и app.y_pred.
    Поддерживает как регрессию, так и классификацию.
    """
    app.fig.clear()
    ax = app.fig.add_subplot(111)

    if app.y_pred is None or app.y_test is None:
        app.metrics_label.config(text="Нет данных для визуализации")
        app.canvas.draw()
        return

    alpha = app.alpha_slider.get()
    code = None
    for c, label in app.available_plots:
        if label == app.plot_var.get() or c == app.plot_var.get():
            code = c
            break

    # Регрессия
    if app.task_var.get() == "Регрессия":
        rmse = np.sqrt(mean_squared_error(app.y_test, app.y_pred))
        mae  = mean_absolute_error(app.y_test, app.y_pred)
        r2   = r2_score(app.y_test, app.y_pred)
        app.metrics_label.config(text=f"RMSE: {rmse:.4f}   MAE: {mae:.4f}   R²: {r2:.3f}")

        if code == "scatter":
            ax.scatter(range(len(app.y_test)), app.y_test, color='green', alpha=alpha, label="Реальные", s=40)
            ax.scatter(range(len(app.y_pred)), app.y_pred, color='red', alpha=alpha, label="Предсказанные", marker='x', s=40)
            ax.set_xlabel('Индекс')
            ax.set_ylabel('Значение')
            ax.set_title('Scatter: Реальные и предсказанные по индексу')
            ax.legend()
        elif code == "xy":
            mask = (~np.isnan(app.y_test) & ~np.isnan(app.y_pred) &
                    ~np.isinf(app.y_test) & ~np.isinf(app.y_pred))
            y_t = app.y_test[mask]
            y_p = app.y_pred[mask]
            m = (y_t.max() - y_t.min()) * 0.05
            ax.scatter(y_t, y_p, s=40, alpha=alpha, color='red', label="Пары")
            ax.scatter(y_t, y_t, s=40, alpha=alpha * 0.5, color='green', label="y = x")
            ax.plot([y_t.min()-m, y_t.max()+m], [y_t.min()-m, y_t.max()+m], 'k--', lw=1.5)
            ax.set_xlabel('Реальные')
            ax.set_ylabel('Предсказанные')
            ax.set_title('Scatter: реальные vs предсказанные')
            ax.legend()
        elif code == "heatmap":
            mask = (~np.isnan(app.y_test) & ~np.isnan(app.y_pred) &
                    ~np.isinf(app.y_test) & ~np.isinf(app.y_pred))
            y_t = app.y_test[mask]
            y_p = app.y_pred[mask]
            m = (y_t.max() - y_t.min()) * 0.05
            hb = ax.hexbin(y_t, y_p, gridsize=30, cmap='Blues', alpha=alpha, mincnt=1)
            app.fig.colorbar(hb, ax=ax)
            ax.plot([y_t.min()-m, y_t.max()+m], [y_t.min()-m, y_t.max()+m], 'k--', lw=1.5)
            ax.set_xlabel('Реальные')
            ax.set_ylabel('Предсказанные')
            ax.set_title('Hexbin: реальные vs предсказанные')
        elif code == "dist":
            ax.hist(app.y_test, bins=30, alpha=0.5, color='green', label="Реальные")
            ax.hist(app.y_pred, bins=30, alpha=0.7, color='red', label="Предсказанные")
            ax.set_xlabel('Значения')
            ax.set_title('Гистограмма распределений')
            ax.legend()
        elif code == "boxplot":
            errs = app.y_pred - app.y_test
            ax.boxplot(errs, vert=False, patch_artist=True,
                       boxprops=dict(facecolor='lightblue', alpha=alpha))
            ax.set_xlabel('Ошибка')
            ax.set_title('Boxplot ошибок')
        elif code == "residuals":
            errs = app.y_pred - app.y_test
            ax.scatter(app.y_pred, errs, alpha=alpha, color='purple')
            ax.axhline(0, color='k', linestyle='--')
            ax.set_xlabel('Предсказанные')
            ax.set_ylabel('Остатки')
            ax.set_title('Residuals plot')

    # Классификация
    else:
        acc  = accuracy_score(app.y_test, app.y_pred)
        prec = precision_score(app.y_test, app.y_pred, average='weighted', zero_division=0)
        rec  = recall_score(app.y_test, app.y_pred, average='weighted', zero_division=0)
        f1   = f1_score(app.y_test, app.y_pred, average='weighted', zero_division=0)
        app.metrics_label.config(text=f"Accuracy: {acc:.3f}   Precision: {prec:.3f}   Recall: {rec:.3f}   F1: {f1:.3f}")

        if code == "heatmap":
            cm = confusion_matrix(app.y_test, app.y_pred)
            im = ax.imshow(cm, cmap=plt.cm.Blues, alpha=alpha)
            app.fig.colorbar(im, ax=ax)
            for i in range(cm.shape[0]):
                for j in range(cm.shape[1]):
                    ax.text(j, i, cm[i, j],
                            ha='center', va='center',
                            color='white' if cm[i, j] > cm.max()/2 else 'black')
            ax.set_xlabel('Предсказанный класс')
            ax.set_ylabel('Реальный класс')
            ax.set_title('Confusion Matrix')
        elif code == "dist":
            uniq, cnts = np.unique(app.y_pred, return_counts=True)
            uniq_t, cnts_t = np.unique(app.y_test, return_counts=True)
            ax.bar(uniq - 0.2, cnts_t, width=0.4, alpha=0.6, color='green', label="Реальные")
            ax.bar(uniq + 0.2, cnts, width=0.4, alpha=0.8, color='red', label="Предсказанные")
            ax.set_xlabel('Класс')
            ax.set_ylabel('Частота')
            ax.set_title('Распределение классов')
            ax.legend()
        elif code == "scatter":
            ax.scatter(range(len(app.y_test)), app.y_test, color='green', alpha=alpha, label="Реальные")
            ax.scatter(range(len(app.y_pred)), app.y_pred, color='red', alpha=alpha, marker='x', label="Предсказанные")
            ax.set_xlabel('Индекс')
            ax.set_ylabel('Класс')
            ax.set_title('Scatter по классам')
            ax.legend()
        elif code == "roc" and len(np.unique(app.y_test)) == 2:
            fpr, tpr, _ = roc_curve(app.y_test, app.y_pred)
            roc_auc = auc(fpr, tpr)
            ax.plot(fpr, tpr, color='darkorange', lw=2, label=f'AUC = {roc_auc:.2f}')
            ax.plot([0,1],[0,1],'k--')
            ax.set_xlabel('False Positive Rate')
            ax.set_ylabel('True Positive Rate')
            ax.set_title('ROC Curve')
            ax.legend(loc='lower right')
        elif code == "pr" and len(np.unique(app.y_test)) == 2:
            p, r, _ = precision_recall_curve(app.y_test, app.y_pred)
            pr_auc = auc(r, p)
            ax.plot(r, p, color='green', lw=2, label=f'AUC = {pr_auc:.2f}')
            ax.set_xlabel('Recall')
            ax.set_ylabel('Precision')
            ax.set_title('Precision-Recall Curve')
            ax.legend(loc='lower left')

    app.canvas.draw()

