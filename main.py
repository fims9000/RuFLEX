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

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class NeuroFuzzyMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("НейроНечёткий Мастер")
        self.root.geometry("1280x720")
        self.root.minsize(1200, 800)

        # State
        self.dataset = None
        self.model = None
        self.scaler = None
        self.y_test = None
        self.y_pred = None
        self.X_test = None
        self.analysis_thread = None
        self.is_training = False

        # --- Верхний блок с кнопками в две строки ---
        top_controls_frame = ctk.CTkFrame(root, fg_color="transparent")
        top_controls_frame.pack(fill="x", padx=12, pady=(8, 4))

        # --- Первая строка кнопок ---
        top_button_row = ctk.CTkFrame(top_controls_frame, fg_color="#262626")
        top_button_row.pack(fill="x")

        self.btn_load = ctk.CTkButton(top_button_row, text="Загрузить данные", command=self.load_data)
        self.btn_analyze = ctk.CTkButton(top_button_row, text="Анализировать", command=self.run_analysis,
                                         state="disabled")
        self.btn_corr = ctk.CTkButton(top_button_row, text="Корреляции", command=self.show_corr_matrix)
        self.btn_xai = ctk.CTkButton(top_button_row, text="XAI анализ", command=self.run_xai)
        self.btn_export = ctk.CTkButton(top_button_row, text="Экспорт правил", command=self.export_rules,
                                        state="disabled")

        buttons_row1 = (self.btn_load, self.btn_analyze, self.btn_corr, self.btn_xai, self.btn_export)
        for btn in buttons_row1:
            btn.pack(side="left", padx=8, pady=5)

        # --- Вторая строка кнопок и индикатор выполнения ---
        bottom_button_row = ctk.CTkFrame(top_controls_frame, fg_color="#262626")
        bottom_button_row.pack(fill="x", pady=(4, 0))

        self.btn_save_model = ctk.CTkButton(bottom_button_row, text="Сохранить модель", command=self.save_model,
                                            state="disabled")
        self.btn_load_model = ctk.CTkButton(bottom_button_row, text="Загрузить модель", command=self.load_model)
        self.btn_predict = ctk.CTkButton(bottom_button_row, text="Анализ с моделью",
                                         command=self.analyze_with_loaded_model, state="disabled")
        self.btn_export_preds = ctk.CTkButton(bottom_button_row, text="Экспорт предсказаний",
                                              command=self.export_predictions, state="disabled")

        buttons_row2 = (self.btn_save_model, self.btn_load_model, self.btn_predict, self.btn_export_preds)
        for btn in buttons_row2:
            btn.pack(side="left", padx=8, pady=5)

        # Индикатор выполнения справа во второй строке
        self.progress_label = ctk.CTkLabel(bottom_button_row, text="Ожидание действия", font=("Arial", 14, "bold"))
        self.progress_label.pack(side="right", padx=18)
        self.progress = ctk.CTkProgressBar(bottom_button_row, width=260, height=15)
        self.progress.pack(side="right", padx=10)
        self.progress.set(0)

        # --- Центральная зона: параметр-панель + график + текст ---
        center = ctk.CTkFrame(root, fg_color="#262626")
        center.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        # БОКОВАЯ ПАНЕЛЬ С ПАРАМЕТРАМИ (слева)
        configbar = ctk.CTkFrame(center, width=140, fg_color="#262626")
        configbar.pack(side="left", fill="y", padx=(0, 5), pady=0)
        configbar.pack_propagate(False)

        ctk.CTkLabel(configbar, text="Параметры модели", font=("Arial", 13, "bold")).pack(padx=8, pady=(8, 0),
                                                                                          anchor="w")
        # Параметры — вертикально c отступами
        row_pad = 7
        ctk.CTkLabel(configbar, text="Тип задачи:").pack(anchor="w", padx=8, pady=(16, 2))
        self.task_var = ctk.StringVar(value="Регрессия")
        self.task_combo = ctk.CTkComboBox(configbar, variable=self.task_var, values=["Регрессия", "Классификация"],
                                          width=180)
        self.task_combo.pack(padx=10, pady=(0, row_pad))

        ctk.CTkLabel(configbar, text="Число правил:").pack(anchor="w", padx=8)
        self.num_rules = ctk.CTkEntry(configbar, width=70)
        self.num_rules.insert(0, "10")
        self.num_rules.pack(padx=10, pady=(0, row_pad))

        ctk.CTkLabel(configbar, text="Тип MF:").pack(anchor="w", padx=8)
        self.mf_var = ctk.StringVar(value="Gaussian")
        self.mf_combo = ctk.CTkComboBox(configbar, variable=self.mf_var, values=["Gaussian", "Sigmoid","Trapezoidal","Triangular","GBell","PiShaped","SShaped","ZShaped","Linear"], width=110)
        self.mf_combo.pack(padx=10, pady=(0, row_pad))

        ctk.CTkLabel(configbar, text="Эпохи:").pack(anchor="w", padx=8)
        self.epochs = ctk.CTkEntry(configbar, width=70)
        self.epochs.insert(0, "100")
        self.epochs.pack(padx=10, pady=(0, row_pad))

        ctk.CTkLabel(configbar, text="Batch size:").pack(anchor="w", padx=8)
        self.batch_size = ctk.CTkEntry(configbar, width=70)
        self.batch_size.insert(0, "32")
        self.batch_size.pack(padx=10, pady=(0, row_pad))

        ctk.CTkLabel(configbar, text="Learning rate:").pack(anchor="w", padx=8)
        self.lr = ctk.CTkEntry(configbar, width=90)
        self.lr.insert(0, "0.01")
        self.lr.pack(padx=10, pady=(0, 10))

        # Label и поле для patience
        ctk.CTkLabel(configbar, text="N_patience:").pack(anchor="w", padx=8)
        self.n_patience = ctk.CTkEntry(configbar, width=90)
        self.n_patience.insert(0, "10")
        self.n_patience.pack(padx=10, pady=(0, 10))

        ctk.CTkLabel(configbar, text="Optim:").pack(anchor="w", padx=8)
        self.optim_var = ctk.StringVar(value="Adam")
        self.optim_combo = ctk.CTkComboBox(configbar, variable=self.optim_var, values=["Adam", "SGD", "RMSprop", "Adagrad", "AdamW", "Adadelta","Adamax","NAdam","Rprop",'ASGD'], width=110)
        self.optim_combo.pack(padx=10, pady=(0, row_pad))

        # --- ЦЕНТР: график --- (теперь больше места!)
        graph_col = ctk.CTkFrame(center, width=600)
        graph_col.pack(side="left", fill="both", expand=True, padx=(0, 16))
        graph_col.pack_propagate(False)
        ctk.CTkLabel(graph_col, text="Визуализация результата", font=("Arial", 14, "bold")).pack(anchor="w", padx=12,
                                                                                                 pady=(10, 0))

        # matplotlib canvas (80% ширины)
        self.fig = plt.Figure(figsize=(8.5, 5.4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_col)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(14, 8))

        # --- Управляющая панель для графика ---
        ctrl = ctk.CTkFrame(graph_col)
        ctrl.pack(fill="x", pady=(0, 0))
        self.plot_var = ctk.StringVar(value="xy")
        self.plot_combo = ctk.CTkComboBox(
            ctrl, variable=self.plot_var, values=[], width=320,
            command=lambda val: self.visualize_results()
        )
        self.plot_combo.pack(side="left", padx=8)
        ctk.CTkLabel(ctrl, text="Прозрачность:").pack(side="left", padx=11)
        self.alpha_slider = ctk.CTkSlider(ctrl, from_=0.1, to=1.0, number_of_steps=18, width=145,
                                          command=self.change_alpha)
        self.alpha_slider.set(1.0)
        self.alpha_slider.pack(side="left", padx=12)
        self.metrics_label = ctk.CTkLabel(graph_col, text="", font=("Arial", 14, "bold"), text_color="#25D356")
        self.metrics_label.pack(anchor="w", fill="x", pady=(7, 2), padx=10)

        # --- ПРАВАЯ колонка: большие текстовые блоки ---
        text_col = ctk.CTkFrame(center, width=550, fg_color="#262626")
        text_col.pack(side="left", fill="both", expand=False, padx=(0, 0))
        text_col.pack_propagate(False)

        # Сначала статистика
        ctk.CTkLabel(text_col, text="Статистика", font=("Arial", 13, "bold")).pack(anchor="nw", padx=12, pady=(12, 0))
        self.text_stats = ctk.CTkTextbox(text_col, font=("Consolas", 12), wrap="word", height=170)
        self.text_stats.pack(fill="both", expand=False, padx=12, pady=(2, 16))

        # Затем правила
        ctk.CTkLabel(text_col, text="Человекочитаемые правила ANFIS", font=("Arial", 13, "bold")).pack(anchor="nw",
                                                                                                       padx=12,
                                                                                                       pady=(0, 0))
        self.text_rules = ctk.CTkTextbox(text_col, font=("Consolas", 13), wrap="word", height=190)
        self.text_rules.pack(fill="both", expand=True, padx=12, pady=(2, 18))

        # --- Нижний статус-бар ---
        bottom = ctk.CTkFrame(root, fg_color="#262626")
        bottom.pack(fill="x", pady=(2, 6))
        self.status = ctk.CTkLabel(bottom, text="Готов к работе", anchor="w")
        self.status.pack(fill="x", expand=True, padx=10, pady=6)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ... (остальные методы класса остаются без изменений) ...

    def load_data(self):
        fp = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx *.xls"), ("All", "*.*")])
        if not fp: return
        self.reset_progress()
        self.progress_label.configure(text="Загрузка данных...")
        self.root.update_idletasks()

        self.dataset = load_dataset(fp)
        stats = get_basic_stats(self.dataset)
        self.text_stats.delete(1.0, "end")
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
                float(self.lr.get()),
                int(self.n_patience.get()),
                self.optim_var.get()
            )
            self.model, self.scaler = result['model'], result['scaler']
            self.y_test, self.y_pred = result['y_test'], result['y_pred']
            self.X_test=result['X_test']
            self.status.configure(text="Извлечение правил...")
            params = get_model_params_dict(
                self.model, self.task_var.get(), self.dataset,
                self.num_rules.get(), self.mf_var.get(),
                self.epochs.get(), self.batch_size.get(), self.lr.get(),self.n_patience.get(), self.optim_var.get()
            )
            rules = extract_human_rules(self.model, self.dataset, params)
            self.text_rules.delete(1.0, "end")
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
                ("step", "Степень уверенности"),
                ('loss', 'loss_history'),
                ("heatmap", "Heatmap (hexbin)"),
                ("dist", "Гистограмма распределений"),
                ("boxplot", "Boxplot ошибок"),
                ("residuals", "Residuals plot (остатки)")
            ]
        else:
            self.available_plots = [
                ("heatmap", "Матрица ошибок (confusion matrix)"),
                ('loss', 'loss_history'),
                ("dist", "Гистограмма по классам"),
                ("scatter", "Scatter по классам"),
                ("step", "Степень уверенности"),
            ]
            if self.y_test is not None and len(np.unique(self.y_test)) == 2:
                self.available_plots += [
                    ("roc", "ROC-кривая"),
                    ("pr", "Precision-Recall")
                ]
        value_list = [label for _, label in self.available_plots]
        self.plot_combo.configure(values=value_list)

    def visualize_results(self):
        visualize_results(self,self.model,self.X_test)

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
            rules = self.text_rules.get(1.0, "end")
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

        y_pred = predict_with_model(self.model, self.scaler, self.dataset)
        self.y_pred = y_pred

        params = get_model_params_dict(
            self.model, self.task_var.get(), self.dataset,
            self.num_rules.get(), self.mf_var.get(),
            self.epochs.get(), self.batch_size.get(), self.lr.get(), self.n_patience.get(), self.optim_var.get()
        )
        rules = extract_human_rules(self.model, self.dataset, params)
        self.text_rules.delete(1.0, "end")
        self.text_rules.insert("end", rules)
        self.update_plot_options()
        values = self.plot_combo.cget("values")
        if values:
            self.plot_combo.set(values[0])

        self.progress.set(100)
        self.progress_label.configure(text="Анализ завершён")
        self.status.configure(text="Анализ завершён (загруженная модель)")
        self.btn_export_preds.configure(state="normal")
        self.btn_export.configure(state="normal")

    def run_xai(self):
        from xai_utils import show_xai_window, explain_shap
        if self.model is None or self.dataset is None:
            messagebox.showwarning("Нет модели/данных", "Сначала обучите модель и загрузите данные")
            return
        self.xai_opened = True
        # Подготовка данных
        X = self.dataset.iloc[:, :-1].copy()
        if 'Unnamed: 0' in X.columns:
            X = X.drop(columns=['Unnamed: 0'])
        X = X.select_dtypes(include=[np.number])
        feature_names = X.columns.tolist()
        # Добавляем ANFIS-правила
        y_pred = predict_with_model(self.model, self.scaler, self.dataset)
        self.y_pred = y_pred
        rules = extract_human_rules(self.model, self.dataset)
        # Получаем графики и текстовые выводы
        shap_plots, shap_text = explain_shap(rules, self.model, self.scaler, X, sample_size=100,
                                             feature_names=feature_names)
        def on_xai_closed():
            self.xai_opened = False
            self.root.focus_force()

        # Открываем красивое XAI-окно
        show_xai_window(self.root, shap_plots, shap_text, on_close=on_xai_closed)

    def on_close(self):
        self.stop_requested = True  # Установить флаг на останов потоков
        # Корректно прервать анализ, если он активен
        if self.analysis_thread and self.analysis_thread.is_alive():
            try:
                self.analysis_thread.join(timeout=2)
            except Exception:
                pass  # На всякий случай игнорируем ошибки
        # Остановить все запланированные after (если есть), чтобы не было ошибок после destroy
        try:
            if hasattr(self, "some_after_id"):
                self.root.after_cancel(self.some_after_id)
        except Exception:
            pass
        # Завершить основной цикл и закрыть окно
        self.root.quit()


if __name__ == "__main__":
    root = ctk.CTk()
    app = NeuroFuzzyMaster(root)
    root.mainloop()
