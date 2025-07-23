import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
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
        self.X_test = None
        self.analysis_thread = None
        self.is_training = False

        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("green.Horizontal.TProgressbar", foreground='green', background='green', thickness=30)
        style.configure("TLabel", font=("Arial", 12))
        style.configure("TButton", font=("Arial", 12))
        style.configure("TCombobox", font=("Arial", 12))

        # Top frames
        top1 = ttk.Frame(root); top1.pack(fill=tk.X, padx=10, pady=(5,0))
        top2 = ttk.Frame(root); top2.pack(fill=tk.X, padx=10, pady=(0,5))

        self.btn_load = ttk.Button(top1, text="Загрузить данные", command=self.load_data)
        self.btn_load.pack(side=tk.LEFT, padx=5)
        self.btn_analyze = ttk.Button(top1, text="Выполнить анализ", command=self.run_analysis, state=tk.DISABLED)
        self.btn_analyze.pack(side=tk.LEFT, padx=5)
        self.btn_corr = ttk.Button(top1, text="Корреляционная матрица", command=self.show_corr_matrix)
        self.btn_corr.pack(side=tk.LEFT, padx=5)
        self.btn_export = ttk.Button(top1, text="Экспорт правил", command=self.export_rules, state=tk.DISABLED)
        self.btn_export.pack(side=tk.LEFT, padx=5)
        self.progress = ttk.Progressbar(top1, length=200, style="green.Horizontal.TProgressbar", mode='determinate')
        self.progress.pack(side=tk.RIGHT, padx=5)
        self.progress_label = ttk.Label(top1, text="Ожидание действия", font=("Arial",12,"bold"))
        self.progress_label.pack(side=tk.RIGHT, padx=10)

        self.btn_save_model = ttk.Button(top2, text="Сохранить модель", command=self.save_model, state=tk.DISABLED)
        self.btn_save_model.pack(side=tk.LEFT, padx=5)
        self.btn_load_model = ttk.Button(top2, text="Загрузить модель", command=self.load_model)
        self.btn_load_model.pack(side=tk.LEFT, padx=5)
        self.btn_predict = ttk.Button(top2, text="Анализировать с моделью", command=self.analyze_with_loaded_model, state=tk.DISABLED)
        self.btn_predict.pack(side=tk.LEFT, padx=5)
        self.btn_export_preds = ttk.Button(top2, text="Выгрузить предсказания", command=self.export_predictions, state=tk.DISABLED)
        self.btn_export_preds.pack(side=tk.LEFT, padx=5)

        # Model parameters
        params = ttk.LabelFrame(root, text="Параметры нейронечёткой системы", padding=8)
        params.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(params, text="Тип задачи:").grid(row=0,column=0,sticky="e",padx=5)
        self.task_var = tk.StringVar(value="Регрессия")
        self.task_combo = ttk.Combobox(params, textvariable=self.task_var, values=["Регрессия","Классификация"], state="readonly", width=14)
        self.task_combo.grid(row=0,column=1,padx=5)

        ttk.Label(params, text="Правил:").grid(row=0,column=2,sticky="e",padx=5)
        self.num_rules = ttk.Entry(params, width=5); self.num_rules.insert(0,"10")
        self.num_rules.grid(row=0,column=3,padx=5)

        ttk.Label(params, text="Функция принадлежности:").grid(row=0,column=4,sticky="e",padx=5)
        self.mf_var = tk.StringVar(value="Gaussian")
        self.mf_combo = ttk.Combobox(params, textvariable=self.mf_var, values=["Gaussian","Sigmoid"], state="readonly", width=10)
        self.mf_combo.grid(row=0,column=5,padx=5)

        ttk.Label(params, text="Эпохи:").grid(row=0,column=6,sticky="e",padx=5)
        self.epochs = ttk.Entry(params, width=5); self.epochs.insert(0,"100")
        self.epochs.grid(row=0,column=7,padx=5)

        ttk.Label(params, text="Батч:").grid(row=0,column=8,sticky="e",padx=5)
        self.batch_size = ttk.Entry(params, width=5); self.batch_size.insert(0,"32")
        self.batch_size.grid(row=0,column=9,padx=5)

        ttk.Label(params, text="Learning rate:").grid(row=0,column=10,sticky="e",padx=5)
        self.lr = ttk.Entry(params, width=7); self.lr.insert(0,"0.01")
        self.lr.grid(row=0,column=11,padx=5)

        # Label и поле для patience
        ttk.Label(params, text="N_patience:").grid(row=0,column=12,sticky="e",padx=5)
        self.n_patience = ttk.Entry(params, width=7); self.n_patience.insert(0, "10")
        self.n_patience.grid(row=0,column=13,padx=5)

        ttk.Label(params, text="Optim:").grid(row=0,column=14,sticky="e",padx=5)
        self.optim_var = tk.StringVar(value="Adam")
        self.optim_combo=ttk.Combobox(params, textvariable=self.optim_var, values=["Adam", "SGD", "RMSprop", "Adagrad", "AdamW", "Adadelta", "Adamax",
                                                   "NAdam", "Rprop", 'ASGD'], state="readonly", width=10)
        self.optim_combo.grid(row=0, column=15, padx=5)
        # Center panes
        center = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        center.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

        # Left panel
        left = ttk.Frame(center); center.add(left, weight=1)
        stats_frame = ttk.LabelFrame(left, text="Статистика и структура данных", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0,10))
        self.text_stats = scrolledtext.ScrolledText(stats_frame, height=12, font=("Consolas",11))
        self.text_stats.pack(fill=tk.BOTH, expand=True)

        rules_frame = ttk.LabelFrame(left, text="Человекочитаемые правила", padding=10)
        rules_frame.pack(fill=tk.BOTH, expand=True)
        self.text_rules = scrolledtext.ScrolledText(rules_frame, height=10, font=("Consolas",11))
        self.text_rules.pack(fill=tk.BOTH, expand=True)

        # Right panel
        right = ttk.Frame(center); center.add(right, weight=2)
        viz = ttk.LabelFrame(right, text="Визуализация", padding=10)
        viz.pack(fill=tk.BOTH, expand=True)

        self.fig = plt.Figure(figsize=(8,5),dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=viz)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        ctrl = ttk.Frame(viz); ctrl.pack(fill=tk.X, pady=(10,0))
        self.plot_var = tk.StringVar(value="xy")
        self.plot_combo = ttk.Combobox(ctrl, textvariable=self.plot_var, state="readonly", width=32)
        self.plot_combo.pack(side=tk.LEFT, padx=5)
        self.plot_combo.bind("<<ComboboxSelected>>", lambda e: self.visualize_results())

        ttk.Label(ctrl, text="Прозрачность:").pack(side=tk.LEFT, padx=5)
        self.alpha_slider = tk.Scale(ctrl, from_=0.1, to=1.0, resolution=0.05, orient=tk.HORIZONTAL, length=120, command=self.change_alpha)
        self.alpha_slider.set(1.0)
        self.alpha_slider.pack(side=tk.LEFT, padx=5)

        self.metrics_label = ttk.Label(viz, text="", font=("Arial",13,"bold"), foreground="#228B22")
        self.metrics_label.pack(fill=tk.X, pady=(10,0))

        # Bottom
        bottom = ttk.Frame(root, padding=10)
        bottom.pack(fill=tk.X)
        self.status = ttk.Label(bottom, text="Готов к работе", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(fill=tk.X, expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_data(self):
        fp = filedialog.askopenfilename(filetypes=[("CSV","*.csv"),("Excel","*.xlsx *.xls"),("All","*.*")])
        if not fp: return
        self.reset_progress()
        self.progress_label.config(text="Загрузка данных...")
        self.root.update_idletasks()

        self.dataset = load_dataset(fp)
        stats = get_basic_stats(self.dataset)
        self.text_stats.delete(1.0, tk.END)
        self.text_stats.insert(tk.END, stats)
        self.btn_analyze.config(state=tk.NORMAL)
        self.btn_predict.config(state=tk.NORMAL if self.model else tk.DISABLED)
        self.status.config(text=f"Данные загружены: {fp}")

        self.progress["value"] = 100
        self.progress_label.config(text="Данные загружены")
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
            self.status.config(text=f"Предсказания сохранены: {fp}")
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", str(e))

    def run_analysis(self):
        if self.dataset is None: return
        self.is_training = True
        self.btn_analyze.config(state=tk.DISABLED)
        self.btn_save_model.config(state=tk.DISABLED)
        self.start_indeterminate()
        self.analysis_thread = threading.Thread(target=self._run_analysis_thread, daemon=True)
        self.analysis_thread.start()

    def start_indeterminate(self):
        self.progress.config(mode='indeterminate')
        self.progress.start(10)
        self.progress_label.config(text="Обучение модели...")

    def stop_progress(self):
        self.progress.stop()
        self.progress.config(mode='determinate')
        self.progress["value"] = 100
        self.progress_label.config(text="Анализ завершён")
        self.root.update_idletasks()

    def reset_progress(self):
        self.progress.stop()
        self.progress.config(mode='determinate')
        self.progress["value"] = 0
        self.progress_label.config(text="Ожидание действия")
        self.root.update_idletasks()

    def _run_analysis_thread(self):
        try:
            self.status.config(text="Запуск анализа...")
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
            self.status.config(text="Извлечение правил...")
            params = get_model_params_dict(
                self.model, self.task_var.get(), self.dataset,
                self.num_rules.get(), self.mf_var.get(),
                self.epochs.get(), self.batch_size.get(), self.lr.get(),self.n_patience.get(), self.optim_var.get()
            )
            rules = extract_human_rules(self.model, result['X_train'], result['y_train'], self.dataset, params)
            self.text_rules.delete(1.0, tk.END)
            self.text_rules.insert(tk.END, rules)
            self.update_plot_options()

            # Завершение
            self.stop_progress()
            self.status.config(text="Анализ завершен успешно")
            self.btn_export.config(state=tk.NORMAL)
            self.btn_save_model.config(state=tk.NORMAL)
            self.btn_predict.config(state=tk.NORMAL)
            self.plot_combo.current(0)
            self.visualize_results()
        except Exception as e:
            self.reset_progress()
            self.progress_label.config(text="Ошибка анализа")
            messagebox.showerror("Ошибка", f"Ошибка при анализе: {e}")
            self.status.config(text="Ошибка анализа")
        finally:
            self.is_training = False
            self.btn_analyze.config(state=tk.NORMAL)

    def update_plot_options(self):
        if self.task_var.get() == "Регрессия":
            self.available_plots = [
                ("scatter", "Scatter (реальные и предсказанные по индексу)"),
                ("xy", "Scatter (реальные vs предсказанные)"),
                ("heatmap", "Heatmap (hexbin)"),
                ("step", "Степень уверенности"),
                ('loss', 'loss_history'),
                ("dist", "Гистограмма распределений"),
                ("boxplot", "Boxplot ошибок"),
                ("residuals", "Residuals plot (остатки)")
            ]
        else:
            self.available_plots = [
                ("heatmap", "Матрица ошибок (confusion matrix)"),
                ("dist", "Гистограмма по классам"),
                ("scatter", "Scatter по классам"),
                ("step", "Степень уверенности"),
                ('loss', 'loss_history'),
            ]
            if self.y_test is not None and len(np.unique(self.y_test)) == 2:
                self.available_plots += [
                    ("roc", "ROC-кривая"),
                    ("pr", "Precision-Recall")
                ]
        self.plot_combo["values"] = [label for _, label in self.available_plots]
        self.plot_combo.current(0)

    def visualize_results(self):
        visualize_results(self,self.model,self.X_test)

    def change_alpha(self,val):
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
        if not self.model:
            messagebox.showwarning("Нет модели", "Сначала обучите модель")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".pkl", filetypes=[("Pickle", "*.pkl"), ("All", "*.*")])
        if not fp: return
        save_full_model(self.model, self.scaler, fp)
        self.status.config(text=f"Модель сохранена: {fp}")

    def load_model(self):
        fp = filedialog.askopenfilename(filetypes=[("Pickle", "*.pkl"), ("All", "*.*")])
        if not fp: return
        self.reset_progress()
        self.progress_label.config(text="Загрузка модели...")
        self.progress["value"] = 50
        self.root.update_idletasks()

        self.model, self.scaler = load_full_model(fp)
        self.stop_progress()
        self.status.config(text=f"Модель загружена: {fp}")
        self.btn_save_model.config(state=tk.NORMAL)
        self.btn_predict.config(state=tk.NORMAL)
        messagebox.showinfo("Готово", "Модель загружена")

    def analyze_with_loaded_model(self):
        if not self.model or self.dataset is None:
            messagebox.showwarning("Нет модели/данных", "Сначала загрузите модель и данные")
            return
        self.reset_progress()
        self.progress_label.config(text="Анализ с загруженной моделью...")
        self.progress["value"] = 50
        self.root.update_idletasks()

        y_pred = predict_with_model(self.model, self.scaler, self.dataset)
        self.y_pred, = y_pred

        rules = extract_human_rules(self.model, self.dataset.iloc[:, :-1], self.y_pred, self.dataset)
        self.text_rules.delete(1.0, tk.END)
        self.text_rules.insert(tk.END, rules)
        self.update_plot_options()
        self.plot_combo.current(0)

        self.progress["value"] = 100
        self.progress_label.config(text="Анализ завершён")
        self.status.config(text="Анализ завершён (загруженная модель)")
        self.btn_export_preds.config(state=tk.NORMAL)

    def on_close(self):
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = NeuroFuzzyMaster(root)
    root.mainloop()

