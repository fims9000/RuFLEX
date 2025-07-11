import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
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
import threading
import numpy as np
import openpyxl

class NeuroFuzzyMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("НейроНечёткий Мастер")
        self.root.geometry("1280x900")
        self.root.minsize(1100, 700)
        self.dataset = None
        self.model = None
        self.scaler = None
        self.model_params = None
        self.alpha = 1.0
        self.available_plots = []
        self.y_test = None
        self.y_pred = None
        self.classes_ = None
        self.progress_max = 100
        self.epochs_total = 100
        self.analysis_thread = None

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("green.Horizontal.TProgressbar", foreground='green', background='green', thickness=30)
        style.configure("TLabel", font=("Arial", 12))
        style.configure("TButton", font=("Arial", 12))
        style.configure("TCombobox", font=("Arial", 12))

        # Верхняя панель
        top_frame1 = ttk.Frame(root)
        top_frame1.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 0))
        top_frame2 = ttk.Frame(root)
        top_frame2.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 5))
        self.btn_load = ttk.Button(top_frame1, text="Загрузить данные", command=self.load_data)
        self.btn_load.pack(side=tk.LEFT, padx=5)
        self.btn_analyze = ttk.Button(top_frame1, text="Выполнить анализ", command=self.run_analysis, state=tk.DISABLED)
        self.btn_analyze.pack(side=tk.LEFT, padx=5)
        self.btn_corr = ttk.Button(top_frame1, text="Корреляционная матрица", command=self.show_corr_matrix)
        self.btn_corr.pack(side=tk.LEFT, padx=5)
        self.btn_export = ttk.Button(top_frame1, text="Экспорт правил", command=self.export_rules, state=tk.DISABLED)
        self.btn_export.pack(side=tk.LEFT, padx=5)
        self.progress = ttk.Progressbar(top_frame1, orient=tk.HORIZONTAL, length=200, mode='determinate',
                                        style="green.Horizontal.TProgressbar")
        self.progress.pack(side=tk.RIGHT, padx=5)
        self.progress_label = ttk.Label(top_frame1, text="Ожидание действия", font=("Arial", 12, "bold"))
        self.progress_label.pack(side=tk.RIGHT, padx=10)

        # Второй ряд
        self.btn_save_model = ttk.Button(top_frame2, text="Сохранить модель", command=self.save_model,
                                         state=tk.DISABLED)
        self.btn_save_model.pack(side=tk.LEFT, padx=5)
        self.btn_load_model = ttk.Button(top_frame2, text="Загрузить модель", command=self.load_model)
        self.btn_load_model.pack(side=tk.LEFT, padx=5)
        self.btn_predict = ttk.Button(top_frame2, text="Анализировать с моделью",
                                      command=self.analyze_with_loaded_model, state=tk.DISABLED)
        self.btn_predict.pack(side=tk.LEFT, padx=5)
        self.btn_export_predictions = ttk.Button(top_frame2, text="Выгрузить предсказания",
                                                 command=self.export_predictions, state=tk.DISABLED)
        self.btn_export_predictions.pack(side=tk.LEFT, padx=5)

        # Параметры модели
        params_frame = ttk.LabelFrame(root, text="Параметры нейронечёткой системы", padding=8)
        params_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        ttk.Label(params_frame, text="Тип задачи:").grid(row=0, column=0, padx=5, sticky="e")
        self.task_var = tk.StringVar(value="Регрессия")
        self.task_combo = ttk.Combobox(params_frame, textvariable=self.task_var,
                                       values=["Регрессия", "Классификация"], width=14, state="readonly")
        self.task_combo.grid(row=0, column=1, padx=5)
        ttk.Label(params_frame, text="Правил:").grid(row=0, column=2, padx=5, sticky="e")
        self.num_rules = ttk.Entry(params_frame, width=5)
        self.num_rules.insert(0, "10")
        self.num_rules.grid(row=0, column=3, padx=5)
        ttk.Label(params_frame, text="Функция принадлежности:").grid(row=0, column=4, padx=5, sticky="e")
        self.mf_var = tk.StringVar(value="Gaussian")
        self.mf_combo = ttk.Combobox(params_frame, textvariable=self.mf_var,
                                     values=["Gaussian", "Sigmoid"], width=10, state="readonly")
        self.mf_combo.grid(row=0, column=5, padx=5)
        ttk.Label(params_frame, text="Эпохи:").grid(row=0, column=6, padx=5, sticky="e")
        self.epochs = ttk.Entry(params_frame, width=5)
        self.epochs.insert(0, "100")
        self.epochs.grid(row=0, column=7, padx=5)
        ttk.Label(params_frame, text="Батч:").grid(row=0, column=8, padx=5, sticky="e")
        self.batch_size = ttk.Entry(params_frame, width=5)
        self.batch_size.insert(0, "32")
        self.batch_size.grid(row=0, column=9, padx=5)
        ttk.Label(params_frame, text="Learning rate:").grid(row=0, column=10, padx=5, sticky="e")
        self.lr = ttk.Entry(params_frame, width=7)
        self.lr.insert(0, "0.01")
        self.lr.grid(row=0, column=11, padx=5)

        # Центральная область
        center_frame = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        center_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

        # Левая панель
        left_panel = ttk.Frame(center_frame)
        center_frame.add(left_panel, weight=1)
        stats_frame = ttk.LabelFrame(left_panel, text="Статистика и структура данных", padding=10)
        stats_frame.pack(fill=tk.BOTH, expand=False, pady=(0,10))
        self.text_stats = scrolledtext.ScrolledText(stats_frame, height=12, font=("Consolas", 11), wrap=tk.WORD)
        self.text_stats.pack(fill=tk.BOTH, expand=True)
        rules_frame = ttk.LabelFrame(left_panel, text="Человекочитаемые правила нейронечёткой системы", padding=10)
        rules_frame.pack(fill=tk.BOTH, expand=True)
        self.text_rules = scrolledtext.ScrolledText(rules_frame, height=10, font=("Consolas", 11), wrap=tk.WORD)
        self.text_rules.pack(fill=tk.BOTH, expand=True)

        # Правая панель
        right_panel = ttk.Frame(center_frame)
        center_frame.add(right_panel, weight=2)
        viz_frame = ttk.LabelFrame(right_panel, text="Визуализация", padding=10)
        viz_frame.pack(fill=tk.BOTH, expand=True)
        self.fig = plt.Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=viz_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        ctrl_frame = ttk.Frame(viz_frame)
        ctrl_frame.pack(fill=tk.X, pady=(10,0))
        self.plot_var = tk.StringVar(value="xy")
        self.plot_combo = ttk.Combobox(ctrl_frame, textvariable=self.plot_var, state="readonly", width=32)
        self.plot_combo.pack(side=tk.LEFT, padx=5)
        self.plot_combo.bind("<<ComboboxSelected>>", lambda e: self.visualize_results())
        ttk.Label(ctrl_frame, text="Прозрачность:").pack(side=tk.LEFT, padx=5)
        self.alpha_slider = tk.Scale(ctrl_frame, from_=0.1, to=1.0, resolution=0.05,
                                     orient=tk.HORIZONTAL, length=120, command=self.change_alpha)
        self.alpha_slider.set(1.0)
        self.alpha_slider.pack(side=tk.LEFT, padx=5)
        self.metrics_label = ttk.Label(viz_frame, text="", font=("Arial", 13, "bold"), foreground="#228B22")
        self.metrics_label.pack(fill=tk.X, pady=(10,0))

        # Нижняя панель
        bottom_frame = ttk.Frame(root, padding=10)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status = ttk.Label(bottom_frame, text="Готов к работе", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_data(self):
        file_path = filedialog.askopenfilename(filetypes=[
            ("CSV files", "*.csv"),
            ("Excel files", "*.xlsx *.xls"),
            ("All files", "*.*")
        ])
        if not file_path:
            return
        self.progress["value"] = 0
        self.progress_label.config(text="Загрузка данных...")
        self.root.update()
        self.dataset = load_dataset(file_path)
        self.progress["value"] = 30
        stats = get_basic_stats(self.dataset)
        self.text_stats.delete(1.0, tk.END)
        self.text_stats.insert(tk.END, stats)
        self.btn_analyze.config(state=tk.NORMAL)
        self.btn_predict.config(state=tk.NORMAL if self.model is not None else tk.DISABLED)
        self.status.config(text=f"Данные загружены: {file_path}")
        self.progress["value"] = 50
        self.progress_label.config(text="Данные загружены")
        self.dataset = self.dataset.dropna()

    def show_corr_matrix(self):
        show_corr_matrix(self.dataset, self.root)

    def export_predictions(self):
        if self.dataset is None or self.y_pred is None:
            messagebox.showwarning("Нет данных", "Сначала выполните анализ или загрузите модель и данные")
            return
        # Создаём копию исходного датасета
        df_export = self.dataset.copy()
        # Добавляем колонку с предсказаниями
        df_export["Предсказания анфисы"] = self.y_pred
        # Диалог сохранения файла
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return
        # Сохраняем в выбранном формате
        try:
            if file_path.endswith('.csv'):
                df_export.to_csv(file_path, index=False)
            else:
                df_export.to_excel(file_path, index=False, engine='openpyxl')
            self.status.config(text=f"Данные с предсказаниями сохранены: {file_path}")
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", str(e))

    def run_analysis(self):
        self.btn_analyze.config(state=tk.DISABLED)
        self.btn_save_model.config(state=tk.DISABLED)
        self.analysis_thread = threading.Thread(target=self._run_analysis_thread, daemon=True)
        self.analysis_thread.start()
        self.animate_progress()


    def animate_progress(self):
        val = self.progress["value"]
        if val < self.progress_max:
            self.progress["value"] = val + (self.progress_max / max(1, int(self.epochs.get())))
            self.progress_label.config(text=f"Обучение модели: {int(self.progress['value'])}%")
            self.root.after(100, self.animate_progress)
        else:
            self.progress["value"] = self.progress_max
            self.progress_label.config(text="Анализ завершён")

    def _run_analysis_thread(self):
        try:
            self.status.config(text="Запуск анализа...")
            self.progress["value"] = 0
            result = run_neurofuzzy_analysis(
                self.dataset,
                self.task_var.get(),
                int(self.num_rules.get()),
                self.mf_var.get(),
                int(self.epochs.get()),
                int(self.batch_size.get()),
                float(self.lr.get())
            )
            self.model = result['model']
            self.scaler = result['scaler']
            self.y_test = result['y_test']
            self.y_pred = result['y_pred']
            self.classes_ = result.get('classes_', None)
            self.model_params = get_model_params_dict(
                self.model, self.task_var.get(), self.dataset, self.num_rules.get(),
                self.mf_var.get(), self.epochs.get(), self.batch_size.get(), self.lr.get()
            )
            rules = extract_human_rules(self.model, result['X_train'], result['y_train'], self.dataset, self.model_params)
            self.text_rules.delete(1.0, tk.END)
            self.text_rules.insert(tk.END, rules)
            self.update_plot_options()
            self.status.config(text="Анализ завершен успешно")
            self.btn_export.config(state=tk.NORMAL)
            self.btn_save_model.config(state=tk.NORMAL)
            self.btn_predict.config(state=tk.NORMAL)
            self.plot_combo.current(0)
            self.visualize_results()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при анализе: {str(e)}")
            self.status.config(text="Ошибка анализа")
            self.progress["value"] = 0
            self.progress_label.config(text="Ошибка анализа")
        finally:
            self.btn_analyze.config(state=tk.NORMAL)


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
        self.plot_combo["values"] = [label for _, label in self.available_plots]
        self.plot_combo.current(0)

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
            rules = self.text_rules.get(1.0, tk.END)
            f.write(rules)
        self.status.config(text=f"Правила экспортированы: {file_path}")

    def save_model(self):
        if self.model is None:
            messagebox.showwarning("Нет модели", "Сначала обучите модель")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".pkl", filetypes=[("Pickle model", "*.pkl"), ("All files", "*.*")])
        if file_path:
            # Сохраняем всю модель и скейлер
            from neurofuzzy import save_full_model
            save_full_model(self.model, self.scaler, file_path)
            self.status.config(text=f"Модель сохранена: {file_path}")

    def load_model(self):
        file_path = filedialog.askopenfilename(filetypes=[("Pickle model", "*.pkl"), ("All files", "*.*")])
        if not file_path:
            return
        from neurofuzzy import load_full_model
        self.model, self.scaler = load_full_model(file_path)
        self.status.config(text=f"Модель загружена: {file_path}")
        self.btn_save_model.config(state=tk.NORMAL)
        self.btn_predict.config(state=tk.NORMAL)
        messagebox.showinfo("Готово", "Модель успешно загружена.\nТеперь можно анализировать новые данные.")

    def analyze_with_loaded_model(self):
        if self.model is None or self.dataset is None:
            messagebox.showwarning("Нет модели/данных", "Сначала загрузите модель и данные")
            return
        y_pred, y_test = predict_with_model(self.model, self.scaler, self.dataset)
        self.y_pred = y_pred
        self.y_test = y_test
        rules = extract_human_rules(self.model, self.dataset.iloc[:, :-1], self.y_pred, self.dataset)
        self.text_rules.delete(1.0, tk.END)
        self.text_rules.insert(tk.END, rules)
        self.update_plot_options()
        self.plot_combo.current(0)
        self.visualize_results()
        self.status.config(text="Анализ завершён (загруженная модель)")
        self.btn_export_predictions.config(state=tk.NORMAL)

    def on_close(self):
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = NeuroFuzzyMaster(root)
    root.mainloop()

