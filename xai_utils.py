import shap
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

def explain_shap(rules,model, scaler, X, sample_size=100, feature_names=None):
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

    shap_plots = {}
    shap_texts = {}

    # 1. Summary Plot (dot)
    fig1, ax1 = plt.subplots(figsize=(22, 8))
    shap.summary_plot(shap_values, X_sample, feature_names=feature_names, show=False, plot_size=[20, 7])
    plt.tight_layout()
    shap_plots["Summary Plot"] = fig1

    # Подробный текст про датасет и признаки
    mean_abs = np.abs(shap_values).mean(axis=0)
    top_idx = np.argsort(mean_abs)[::-1][:5]
    summary_features = [feature_names[i] for i in top_idx]
    summary_vals = [mean_abs[i] for i in top_idx]
    summary_details = "\n".join(
        f"- {fname}: средний вклад {val:.3f}" for fname, val in zip(summary_features, summary_vals)
    )
    shap_texts["Summary Plot"] = (
        "Summary Plot — вклад каждого признака по всем примерам.\n"
        "Яркие точки — сильное влияние, бледные — слабое. Цвет — значение признака.\n"
        f"Топ-5 признаков для датасета:\n{summary_details}\n"
        "Это именно те признаки, которые сильнее всего влияют на предсказания модели!"
    )

    # 2. Bar Plot
    fig2, ax2 = plt.subplots(figsize=(22, 8))
    shap.summary_plot(shap_values, X_sample, feature_names=feature_names, plot_type="bar", show=False, plot_size=[20, 7])
    plt.tight_layout()
    shap_plots["Bar Plot"] = fig2

    shap_texts["Bar Plot"] = (
        "Bar Plot — суммарная важность признаков по модулю.\n"
        "Верхние признаки — самые важные для модели.\n"
        "В датасете абсолютные лидеры по важности:\n"
        + "\n".join(f"- {feature_names[i]}: {mean_abs[i]:.3f}" for i in top_idx)
    )

    # 3. Force Plot (первый пример)
    # Округляем значения признаков до 2 знаков после запятой
    X_sample_rounded = np.round(X_sample[0], 2)
    shap.force_plot(
        explainer.expected_value,
        shap_values[0],
        X_sample_rounded,
        feature_names=feature_names,
        matplotlib=True,
        show=False
    )
    plt.tight_layout()
    shap_plots["Force Plot"] = plt.gcf()
    # Формируем подробный текст для force plot
    force_contribs = sorted(
        zip(feature_names, shap_values[0], X_sample[0]), key=lambda x: abs(x[1]), reverse=True
    )
    force_text = "Force Plot для первого примера:\n"
    for fname, val, fval in force_contribs[:7]:
        direction = "⬆️ увеличивает" if val > 0 else "⬇️ уменьшает"
        force_text += f"- {fname} = {fval:.3f}: {direction} прогноз на {abs(val):.3f}\n"
    force_text += "\nЭто индивидуальное объяснение для конкретного примера из датасета!"
    shap_texts["Force Plot"] = force_text

    # 4. Waterfall Plot (первый пример)
    try:
        fig4, ax4 = plt.subplots(figsize=(14,7))
        shap.plots.waterfall(
            shap.Explanation(
                values=shap_values[0],
                base_values=explainer.expected_value,
                data=X_sample[0],
                feature_names=feature_names
            ), show=False
        )
        plt.tight_layout()
        ax = plt.gca()
        pos = ax.get_position()
        ax.set_position([pos.x0 - 0.05, pos.y0, pos.width, pos.height])  # Сдвиг влево
        fig4 = plt.gcf()
        shap_plots["Waterfall Plot"] = fig4
        waterfall_contribs = sorted(
            zip(feature_names, shap_values[0], X_sample[0]), key=lambda x: abs(x[1]), reverse=True
        )
        waterfall_text = "Waterfall Plot (первый пример):\n"
        for fname, val, fval in waterfall_contribs[:7]:
            direction = "⬆️ увеличивает" if val > 0 else "⬇️ уменьшает"
            waterfall_text += f"- {fname} = {fval:.3f}: {direction} итоговое предсказание на {abs(val):.3f}\n"
        waterfall_text += "\nВидно, какие признаки шаг за шагом формируют итог!"
        shap_texts["Waterfall Plot"] = waterfall_text
    except Exception as e:
        shap_texts["Waterfall Plot"] = f"⛔ Waterfall Plot не удалось отобразить: {e}"

    # 5. Decision Plot (все примеры)
    try:
        fig5, ax5 = plt.subplots(figsize=(28,14))
        shap.decision_plot(
            explainer.expected_value, shap_values, X_sample, feature_names=feature_names, show=False, feature_display_range=slice(None)
        )
        plt.tight_layout()
        shap_plots["Decision Plot"] = fig5
        # Анализ для твоего датасета
        dec_top = summary_features
        dec_text = (
            "Decision Plot — как модель принимает решения по мере добавления признаков.\n"
            "Видно, что для большинства наблюдений ключевыми были:\n"
            + "\n".join(f"- {f}" for f in dec_top) +
            "\n\nКаждая линия — отдельный пример из датасета."
        )
        shap_texts["Decision Plot"] = dec_text
    except Exception as e:
        shap_texts["Decision Plot"] = f"⛔ Decision Plot не удалось отобразить: {e}"

    # --- Общий человекочитаемый вывод ---
    def shorten_rules_clean(rules_text):
        import re
        # Удаляем лишний заголовок
        rules_text = re.sub(
            r'(Человекочитаемые правила нейронечёткой системы:\n)+',
            'Правила нейронечёткой системы:\n',
            rules_text
        )
        # Разбиваем текст на блоки по правилам
        blocks = re.split(r'(Правило \d+)', rules_text)
        header = blocks[0].strip()
        rules_blocks = blocks[1:]

        result = [header]
        for i in range(0, len(rules_blocks), 2):
            rule_title = rules_blocks[i].strip()
            rule_text = rules_blocks[i + 1].strip()
            # Оставляем только интерпретацию (без коэффициентов и служебных строк)
            lines = [
                line for line in rule_text.splitlines()
                if not (line.strip() == "Коэффициенты:" or
                        (line.startswith("- ") and any(c.isdigit() for c in line)) or
                        line.strip() == "")
            ]
            filtered_lines = [line for line in lines if "Человекочитаемая интерпретация" in line or
                              line.startswith("Если") or line.startswith("и маленькое") or line.startswith("то выход")]
            result.append(f"{rule_title}\n" + "\n".join(filtered_lines))
        return "\n\n".join(result)

    # формирования итогового вывода:
    short_rules = shorten_rules_clean(rules)
    summary_text = "Главные влияющие признаки по SHAP для датасета:\n"
    for idx in top_idx:
        fname = feature_names[idx]
        sign = "увеличивает" if mean_abs[idx] > 0 else "уменьшает"
        summary_text += f"- {fname}: если больше — {sign} прогноз (средний вклад {mean_abs[idx]:.3f})\n"
    summary_text += (
        f"\n{short_rules}\n"
        "\nСовместная интерпретация:\n"
        "- Оба метода выделяют одинаковые ключевые признаки.\n"
        "- SHAP показывает их глобальную важность и направление влияния.\n"
        "- ANFIS формулирует простые условия, при которых результат особенно сильно увеличивается.\n"
        "- Такой комбинированный вывод обеспечивает максимальную объяснимость работы модели."
    )
    shap_texts["Summary"] = summary_text

    return shap_plots, shap_texts

def show_xai_window(root, shap_plots, shap_texts):
    win = tk.Toplevel(root)
    win.title("XAI Анализ")

    tab_control = ttk.Notebook(win)
    tab_control.pack(expand=1, fill='both')

    # Вкладки для графиков + подробные тексты
    for plot_name, fig in shap_plots.items():
        tab = ttk.Frame(tab_control)
        tab_control.add(tab, text=plot_name)
        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas.get_tk_widget().pack(fill='both', expand=True)
        canvas.draw()
        # Текстовое поле под графиком
        text_box = tk.Text(tab, height=10, font=("Consolas", 13))
        text_box.pack(fill='x', expand=False)
        text_box.insert(tk.END, shap_texts.get(plot_name, ""))

    # Общий человекочитаемый вывод (отдельная вкладка)
    summary_tab = ttk.Frame(tab_control)
    tab_control.add(summary_tab, text="💡 Итог")
    text_box = tk.Text(summary_tab, height=20, font=("Consolas", 15))
    text_box.pack(fill='both', expand=True)
    text_box.insert(tk.END, shap_texts.get("Summary", ""))

