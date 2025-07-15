import customtkinter as ctk
from tkinter import filedialog, messagebox
import time
import threading
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from utils import (
    load_dataset, get_basic_stats, show_corr_matrix,
    get_model_params_dict, visualize_results
)
from neurofuzzy import (
    run_neurofuzzy_analysis, extract_human_rules,
    save_full_model, load_full_model, predict_with_model
)

# настройка темы
ctk.set_appearance_mode("dark")

class NeuroFuzzyMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("НейроНечёткий Мастер")
        self.root.geometry("1280x900")
        self.root.minsize(1100, 700)

        # State
        self.dataset = None
        self.model = None
        self.scaler = None
        self.y_test = None
        self.y_pred = None
        self.analysis_thread = None
        self.is_training = False

        # Верхние панели
        top1 = ctk.CTkFrame(root)
        top1.pack(fill="x", padx=10, pady=(5, 0))
        top2 = ctk.CTkFrame(root)
        top2.pack(fill="x", padx=10, pady=(0, 5))

        self.btn_load = ctk.CTkButton(top1, text="Загрузить данные", command=self.load_data)
        self.btn_load.pack(side="left", padx=5)
        self.btn_analyze = ctk.CTkButton(top1, text="Выполнить анализ", command=self.run_analysis, state="disabled")
        self.btn_analyze.pack(side="left", padx=5)
        self.btn_corr = ctk.CTkButton(top1, text="Корреляционная матрица", command=self.show_corr_matrix)
        self.btn_corr.pack(side="left", padx=5)
        self.btn_export = ctk.CTkButton(top1, text="Экспорт правил", command=self.export_rules, state="disabled")
        self.btn_export.pack(side="left", padx=5)
        self.progress_label = ctk.CTkLabel(top1, text="Ожидание действия", font=("Arial", 13, "bold"))
        self.progress_label.pack(side="right", padx=10)

        self.progress = ctk.CTkProgressBar(top1, width=200)
        self.progress.pack(side="right", padx=5)
        self.progress.set(0)

        self.btn_save_model = ctk.CTkButton(top2, text="Сохранить модель", command=self.save_model, state="disabled")
        self.btn_save_model.pack(side="left", padx=5)
        self.btn_load_model = ctk.CTkButton(top2, text="Загрузить модель", command=self.load_model)
        self.btn_load_model.pack(side="left", padx=5)
        self.btn_predict = ctk.CTkButton(top2, text="Анализировать с моделью", command=self.analyze_with_loaded_model,
                                         state="disabled")
        self.btn_predict.pack(side="left", padx=5)
        self.btn_export_preds = ctk.CTkButton(top2, text="Выгрузить предсказания", command=self.export_predictions,
                                              state="disabled")
        self.btn_export_preds.pack(side="left", padx=5)
        self.btn_xai = ctk.CTkButton(top1, text="XAI анализ", command=self.run_xai)
        self.btn_xai.pack(side="left", padx=5)

        # Параметры модели
        params = ctk.CTkFrame(root)
        params.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(params, text="Тип задачи:").grid(row=0, column=0, sticky="e", padx=5)
        self.task_var = ctk.StringVar(value="Регрессия")
        self.task_combo = ctk.CTkComboBox(params, variable=self.task_var, values=["Регрессия", "Классификация"],
                                          width=114)
        self.task_combo.grid(row=0, column=1, padx=5)

        ctk.CTkLabel(params, text="Правил:").grid(row=0, column=2, sticky="e", padx=5)
        self.num_rules = ctk.CTkEntry(params, width=50)
        self.num_rules.insert(0, "10")
        self.num_rules.grid(row=0, column=3, padx=5)

        ctk.CTkLabel(params, text="Функция принадлежности:").grid(row=0, column=4, sticky="e", padx=5)
        self.mf_var = ctk.StringVar(value="Gaussian")
        self.mf_combo = ctk.CTkComboBox(params, variable=self.mf_var, values=["Gaussian", "Sigmoid"], width=85)
        self.mf_combo.grid(row=0, column=5, padx=5)

        ctk.CTkLabel(params, text="Эпохи:").grid(row=0, column=6, sticky="e", padx=5)
        self.epochs = ctk.CTkEntry(params, width=50)
        self.epochs.insert(0, "100")
        self.epochs.grid(row=0, column=7, padx=5)

        ctk.CTkLabel(params, text="Батч:").grid(row=0, column=8, sticky="e", padx=5)
        self.batch_size = ctk.CTkEntry(params, width=50)
        self.batch_size.insert(0, "32")
        self.batch_size.grid(row=0, column=9, padx=5)

        ctk.CTkLabel(params, text="Learning rate:").grid(row=0, column=10, sticky="e", padx=5)
        self.lr = ctk.CTkEntry(params, width=70)
        self.lr.insert(0, "0.01")
        self.lr.grid(row=0, column=11, padx=5)

        # Центр: панель с двумя колонками
        center = ctk.CTkFrame(root)
        center.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Левая панель
        left = ctk.CTkFrame(center, width=900)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=0)
        # Область для статистики
        stats_frame = ctk.CTkFrame(left)
        stats_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(stats_frame, text="Статистика и структура данных", font=("Arial", 13, "bold")).pack(anchor="w",
                                                                                                         padx=8,
                                                                                                         pady=(4, 0))
        self.text_stats = ctk.CTkTextbox(stats_frame, height=200, font=("Consolas", 12), wrap="word")
        self.text_stats.pack(fill="both", expand=True, padx=8, pady=(2, 6))

        # Область для правил
        rules_frame = ctk.CTkFrame(left)
        rules_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(rules_frame, text="Человекочитаемые правила", font=("Arial", 13, "bold")).pack(anchor="w", padx=8,
                                                                                                    pady=(4, 0))
        self.text_rules = ctk.CTkTextbox(rules_frame, height=140, font=("Consolas", 12), wrap="word")
        self.text_rules.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        # Правая панель
        right = ctk.CTkFrame(center, width=400)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0), pady=0)
        viz_frame = ctk.CTkFrame(right)
        viz_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(viz_frame, text="Визуализация", font=("Arial", 13, "bold")).pack(anchor="w", padx=8)
        self.fig = plt.Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=viz_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, pady=(6, 4))

        ctrl = ctk.CTkFrame(viz_frame)
        ctrl.pack(fill="x", pady=(6, 0))
        self.plot_var = ctk.StringVar(value="xy")
        self.plot_combo = ctk.CTkComboBox(ctrl, variable=self.plot_var, values=[], width=250,command=lambda value: self.visualize_results() )   # ← колбэк)
        self.plot_combo.pack(side="left", padx=8)
        ctk.CTkLabel(ctrl, text="Прозрачность:").pack(side="left", padx=7)
        # Slider через CTkSlider
        self.alpha_slider = ctk.CTkSlider(ctrl, from_=0.1, to=1.0, number_of_steps=18, width=120,
                                          command=self.change_alpha)
        self.alpha_slider.set(1.0)
        self.alpha_slider.pack(side="left", padx=7)

        self.metrics_label = ctk.CTkLabel(viz_frame, text="", font=("Arial", 15, "bold"), text_color="#49E426")
        self.metrics_label.pack(fill="x", pady=(10, 0))

        # Нижняя статус-строка
        bottom = ctk.CTkFrame(root)
        bottom.pack(fill="x", pady=(4, 4))
        self.status = ctk.CTkLabel(bottom, text="Готов к работе", anchor="w")
        self.status.pack(fill="x", expand=True, padx=4, pady=4)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_data(self):
        fp = filedialog.askopenfilename(filetypes=[("CSV","*.csv"),("Excel","*.xlsx *.xls"),("All","*.*")])
        if not fp: return
        self.reset_progress()
        self.progress_label.configure(text="Загрузка данных...")
        self.root.update_idletasks()

        self.dataset = load_dataset(fp)
        stats = get_basic_stats(self.dataset)
        self.text_stats.delete(1.0,"end")
        self.text_stats.insert("end", stats)
        self.btn_analyze.configure(state="normal")
        self.btn_predict.configure(state="normal" if self.model else "disabled")
        self.status.configure(text=f"Данные загружены: {fp}")

        self.progress.set(100)
        self.progress_label.configure(text="Данные загружены")
        self.dataset = self.dataset.dropna()

    def show_corr_matrix(self):
        if self.dataset is not None:
            show_corr_matrix(self.dataset, self.root)

    def export_predictions(self):
        if self.dataset is None or self.y_pred is None:
            messagebox.showwarning("Нет данных", "Сначала выполните анализ или загрузите модель и данные")
            return
        df = self.dataset.copy()

        df["Predictions"] = self.y_pred

        fp = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*")]
        )

        if not fp:
            return

        try:
            if fp.endswith('.csv'):
                df.to_csv(fp, index=False)
            else:
                df.to_excel(fp, index=False, engine='openpyxl')
            self.status.configure(text=f"Предсказания сохранены: {fp}")
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", str(e))

    def run_analysis(self):
        if self.dataset is None: return
        self.is_training = True
        self.btn_analyze.configure(state="disabled")
        self.btn_save_model.configure(state="disabled")
        self.start_indeterminate()
        self.analysis_thread = threading.Thread(target=self._run_analysis_thread, daemon=True)
        self.analysis_thread.start()

    def start_indeterminate(self):
        self.progress.configure(mode='indeterminate')
        self.progress.start()
        self.progress_label.configure(text="Обучение модели...")

    def stop_progress(self):
        self.progress.stop()
        self.progress.configure(mode='determinate')
        self.progress.set(100)
        self.progress_label.configure(text="Анализ завершён")
        self.root.update_idletasks()

    def reset_progress(self):
        self.progress.stop()
        self.progress.configure(mode='determinate')
        self.progress.set(0)
        self.progress_label.configure(text="Ожидание действия")
        self.root.update_idletasks()

    def _run_analysis_thread(self):
        try:
            self.status.configure(text="Запуск анализа...")
            result = run_neurofuzzy_analysis(
                self.dataset,
                self.task_var.get(),
                int(self.num_rules.get()),
                self.mf_var.get(),
                int(self.epochs.get()),
                int(self.batch_size.get()),
                float(self.lr.get())
            )
            self.model, self.scaler = result['model'], result['scaler']
            self.y_test, self.y_pred = result['y_test'], result['y_pred']

            self.status.configure(text="Извлечение правил...")
            params = get_model_params_dict(
                self.model, self.task_var.get(), self.dataset,
                self.num_rules.get(), self.mf_var.get(),
                self.epochs.get(), self.batch_size.get(), self.lr.get()
            )
            rules = extract_human_rules(self.model, result['X_train'], result['y_train'], self.dataset, params)
            self.text_rules.delete(1.0,"end")
            self.text_rules.insert("end", rules)
            self.update_plot_options()

            # Завершение
            self.stop_progress()
            self.status.configure(text="Анализ завершен успешно")
            self.btn_export.configure(state="normal")
            self.btn_save_model.configure(state="normal")
            self.btn_predict.configure(state="normal")
            values = self.plot_combo.cget("values")
            if values:
                self.plot_combo.set(values[0])
            self.visualize_results()
        except Exception as e:
            self.reset_progress()
            self.progress_label.configure(text="Ошибка анализа")
            messagebox.showerror("Ошибка", f"Ошибка при анализе: {e}")
            self.status.configure(text="Ошибка анализа")
        finally:
            self.is_training = False
            self.btn_analyze.configure(state="normal")

    def update_plot_options(self):
        if self.task_var.get() == "Регрессия":
            self.available_plots = [
                ("scatter", "Scatter (реальные и предсказанные по индексу)"),
                ("xy", "Scatter (реальные vs предсказанные)"),
                ("heatmap", "Heatmap (hexbin)"),
                ("dist", "Гистограмма распределений"),
                ("boxplot", "Boxplot ошибок"),
                ("residuals", "Residuals plot (остатки)")
            ]
        else:
            self.available_plots = [
                ("heatmap", "Матрица ошибок (confusion matrix)"),
                ("dist", "Гистограмма по классам"),
                ("scatter", "Scatter по классам"),
            ]
            if self.y_test is not None and len(np.unique(self.y_test)) == 2:
                self.available_plots += [
                    ("roc", "ROC-кривая"),
                    ("pr", "Precision-Recall")
                ]
        value_list = [label for _, label in self.available_plots]
        self.plot_combo.configure(values=value_list)

    def visualize_results(self):
        visualize_results(self)

    def change_alpha(self, val):
        self.visualize_results()

    def export_rules(self):
        if self.model is None:
            messagebox.showwarning("Ошибка", "Нет данных для экспорта")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not file_path:
            return
        with open(file_path, 'w', encoding='utf-8') as f:
            rules = self.text_rules.get(1.0,"end")
            f.write(rules)
        self.status.configure(text=f"Правила экспортированы: {file_path}")

    def save_model(self):
        if not self.model:
            messagebox.showwarning("Нет модели", "Сначала обучите модель")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".pkl", filetypes=[("Pickle", "*.pkl"), ("All", "*.*")])
        if not fp: return
        save_full_model(self.model, self.scaler, fp)
        self.status.configure(text=f"Модель сохранена: {fp}")

    def load_model(self):
        fp = filedialog.askopenfilename(filetypes=[("Pickle", "*.pkl"), ("All", "*.*")])
        if not fp: return
        self.reset_progress()
        self.progress_label.configure(text="Загрузка модели...")
        self.progress.set(50)
        self.root.update_idletasks()

        self.model, self.scaler = load_full_model(fp)
        self.stop_progress()
        self.status.configure(text=f"Модель загружена: {fp}")
        self.btn_save_model.configure(state="normal")
        self.btn_predict.configure(state="normal")
        messagebox.showinfo("Готово", "Модель загружена")

    def analyze_with_loaded_model(self):
        if not self.model or self.dataset is None:
            messagebox.showwarning("Нет модели/данных", "Сначала загрузите модель и данные")
            return
        self.reset_progress()
        self.progress_label.configure(text="Анализ с загруженной моделью...")
        self.progress.set(50)
        self.root.update_idletasks()

        y_pred, y_test = predict_with_model(self.model, self.scaler, self.dataset)
        self.y_pred, self.y_test = y_pred, y_test

        rules = extract_human_rules(self.model, self.dataset.iloc[:, :-1], self.y_pred, self.dataset)
        self.text_rules.delete(1.0,"end")
        self.text_rules.insert("end", rules)
        self.update_plot_options()
        values = self.plot_combo.cget("values")
        if values:
            self.plot_combo.set(values[0])
        self.visualize_results()

        self.progress.set(100)
        self.progress_label.configure(text="Анализ завершён")
        self.status.configure(text="Анализ завершён (загруженная модель)")
        self.btn_export_preds.configure(state="normal")

    def run_xai(self):
        from xai_utils import show_xai_window, explain_shap
        if self.model is None or self.dataset is None:
            messagebox.showwarning("Нет модели/данных", "Сначала обучите модель и загрузите данные")
            return
        # Подготовка данных
        X = self.dataset.iloc[:, :-1].copy()
        if 'Unnamed: 0' in X.columns:
            X = X.drop(columns=['Unnamed: 0'])
        X = X.select_dtypes(include=[np.number])
        feature_names = X.columns.tolist()
        # Добавляем ANFIS-правила
        y_pred, y_test = predict_with_model(self.model, self.scaler, self.dataset)
        self.y_pred, self.y_test = y_pred, y_test
        rules = extract_human_rules(self.model, self.dataset.iloc[:, :-1], self.y_pred, self.dataset)
        # Получаем графики и текстовые выводы
        shap_plots, shap_text = explain_shap(rules, self.model, self.scaler, X, sample_size=100, feature_names=feature_names)
        # Открываем красивое XAI-окно
        show_xai_window(self.root, shap_plots, shap_text)

    def on_close(self):
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = NeuroFuzzyMaster(root)
    root.mainloop()