import tkinter as tk
from tkinter import filedialog, ttk
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import time
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.patches import Rectangle

# Используем TkAgg
matplotlib.use("TkAgg")
plt.style.use('dark_background')
# git commit -m "init: Базовая настройка TkAgg и dark_background для matplotlib"

class CSVGraphApp:
    """
    /**
     * Класс CSVGraphApp для отображения state timeline из CSV.
     * По оси X располагаются квадраты, каждый из которых соответствует одному seq.
     * Цвет квадрата определяется итоговым состоянием:
     *   - type = -1 (lost) – красный,
     *   - type = 1 (received) – зеленый,
     *   - type = 2 (resend) – желтый.
     *
     * Логика определения итогового состояния:
     *   Если в группе для seq присутствует хотя бы один event с type=2, итоговый статус = 2.
     *   Иначе, если есть event с type=1, итоговый статус = 1.
     *   Иначе – итоговый статус = -1.
     *
     * Для final_state == 2 tooltip формируется особым образом:
     *   Находится первый event с type=2 и последний event с type=-1, предшествующий ему.
     *   В tooltip выводится: время потери и время восстановления.
     *
     * На нижней части окна отображается сводная таблица подсчета.
     *
     * При запуске программы график не отображается до загрузки CSV.
     */
    """
    def __init__(self, root):
        """
        /**
         * Конструктор класса.
         * @param root Корневое окно Tkinter.
         */
        """
        self.root = root
        self.root.title("State Timeline из CSV")
        self.root.update_idletasks()  # гарантирует получение актуальных размеров экрана
        self.center_half_screen()
        self.root.configure(bg="#2E2E2E")

        self.font = ("Segoe UI", 12)
        self.button_font = ("Segoe UI", 12, "bold")

        # Фрейм для кнопок
        control_frame = tk.Frame(root, bg="#2E2E2E")
        control_frame.pack(pady=10, fill=tk.X)

        self.tooltip_window = None
        self.last_patch = None
        self.update_interval = 0.1  # интервал обновления tooltip (100 мс)
        self.last_update_time = 0
        self.bar_patches = []  # список объектов-квадратов для tooltip
        self.seq_info = []     # список агрегированной информации по seq

        self.select_button = tk.Button(
            control_frame, text="Выбрать CSV файл", command=self.load_csv,
            font=self.button_font, bg="#555555", fg="white", relief=tk.FLAT
        )
        self.select_button.pack(side=tk.LEFT, padx=5)

        self.plot_button = tk.Button(
            control_frame, text="Построить график", command=self.plot_graph,
            state=tk.DISABLED, font=self.button_font, bg="#555555",
            fg="white", relief=tk.FLAT
        )
        self.plot_button.pack(side=tk.LEFT, padx=5)

        self.file_label = tk.Label(
            control_frame, text="Файл не выбран", font=self.font, bg="#2E2E2E", fg="white"
        )
        self.file_label.pack(side=tk.LEFT, padx=10)

        self.create_checkboxes()

        # Область для графика (отображается только после загрузки CSV)
        self.figure, self.ax = plt.subplots(figsize=(8, 4), facecolor="#2E2E2E")
        self.canvas = FigureCanvasTkAgg(self.figure, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.toolbar = NavigationToolbar2Tk(self.canvas, root, pack_toolbar=False)
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.toolbar.configure(bg="#404040")
        for child in self.toolbar.winfo_children():
            if isinstance(child, tk.Button):
                child.config(bg="#555555", fg="white")
            elif isinstance(child, tk.Label):
                child.config(bg="#404040", fg="white")

        self.data = None  # данные CSV
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

        # Цвета для состояний
        self.colors = {
            -1: "#FF0000",  # lost – красный
            1: "#00FF00",   # received – зеленый
            2: "#FFD700"    # resend – желтый
        }
        # Изначально график не рисуется до загрузки CSV
        # git commit -m "feat: Инициализирован интерфейс, область графика и tooltip"

    def center_half_screen(self):
        """
        /**
         * Центрирует окно, устанавливая его размер половиной экрана (но не больше 1280x720).
         */
        """
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = int(screen_width * 0.5)
        height = int(screen_height * 0.5)
        max_width = 1280
        max_height = 720
        width = min(width, max_width)
        height = min(height, max_height)
        x = int((screen_width - width) / 2)
        y = int((screen_height - height) / 2)
        geometry_str = f"{width}x{height}+{x}+{y}"
        print(f"[DEBUG] Устанавливаем geometry: {geometry_str}", flush=True)
        self.root.geometry(geometry_str)
        # git commit -m "refactor: Добавлена функция центрирования окна"

    def create_checkboxes(self):
        """
        /**
         * Создает чекбоксы для выбора информации, отображаемой в tooltip.
         */
        """
        self.check_vars = {
            "timestamp": tk.BooleanVar(value=True),
            "seq": tk.BooleanVar(value=True),
            "type": tk.BooleanVar(value=True),
            "count": tk.BooleanVar(value=True)
        }
        check_frame = tk.Frame(self.root, bg="#2E2E2E")
        check_frame.pack(fill=tk.X, padx=10)
        for key, var in self.check_vars.items():
            cb = ttk.Checkbutton(check_frame, text=key, variable=var, style="TCheckbutton")
            cb.pack(side=tk.LEFT, padx=5)
        # git commit -m "feat: Добавлены чекбоксы для tooltip"

    def load_csv(self):
        """
        /**
         * Загружает CSV-файл и проверяет наличие столбцов 'timestamp', 'seq', 'type'.
         */
        """
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        try:
            print(f"[INFO] Открываем файл: {file_path}", flush=True)
            df = pd.read_csv(file_path)
            if not {"timestamp", "seq", "type"}.issubset(df.columns):
                raise ValueError("CSV не содержит столбцы: timestamp, seq, type")
            df["type"] = df["type"].astype(int)
            if "count" not in df.columns:
                df["count"] = 1
            # Преобразуем timestamp
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")
            df = df.dropna(subset=["timestamp"])
            self.data = df
            self.file_label.config(text=f"Выбран файл: {file_path.split('/')[-1]}")
            self.plot_button.config(state=tk.NORMAL)
            print(f"[INFO] Загружено {len(self.data)} строк. Пример:\n{self.data.head()}", flush=True)
            self.plot_graph()
            # git commit -m "feat: Реализована загрузка и предварительная обработка CSV"
        except Exception as e:
            print(f"[ERROR] Ошибка при загрузке CSV: {e}", flush=True)
            self.file_label.config(text=f"Ошибка: {e}")
            self.plot_button.config(state=tk.DISABLED)
            # git commit -m "fix: Обработка ошибок при загрузке CSV"

    def plot_graph(self):
        """
        /**
         * Строит state timeline:
         * - Группирует данные по 'seq'.
         * - Для каждого seq определяет итоговое состояние:
         *      Если есть event с type=2 (resend) -> итоговый статус 2 (желтый);
         *      иначе если есть event с type=1 (received) -> итоговый статус 1 (зеленый);
         *      иначе -> статус -1 (lost, красный).
         * - Если итоговый статус 2, то в tooltip оставляем только информацию о resend:
         *      определяется время потери (последний event с type=-1 до первого type=2)
         *      и время восстановления (первый event с type=2).
         * - По оси X размещаются квадраты (размер 1x1) для каждого seq, разделенные зазором.
         * - Таймлайн отрисовывается на верхней половине графика.
         * - Устанавливаются xticks с номерами seq.
         * - В нижней части окна выводится сводная таблица подсчета.
         */
        """
        if self.data is None or self.data.empty:
            return

        self.ax.clear()
        self.bar_patches.clear()
        self.seq_info.clear()

        # Группируем данные по seq
        grouped = self.data.groupby("seq")
        for seq, group in grouped:
            group = group.sort_values("timestamp")
            events = group.to_dict('records')
            types = group["type"].tolist()
            # Определяем итоговое состояние:
            if 2 in types:
                final_state = 2
            elif 1 in types:
                final_state = 1
            elif -1 in types:
                final_state = -1
            else:
                final_state = -1

            # Если итоговый статус 2, оставляем только данные о resend
            if final_state == 2:
                resend_event = None
                lost_event = None
                for event in events:
                    if event["type"] == 2:
                        resend_event = event
                        break
                    elif event["type"] == -1:
                        lost_event = event
                if lost_event and resend_event:
                    tooltip_text = (f"Seq: {seq}\n"
                                    f"Lost: {lost_event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                                    f"Recovered: {resend_event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    tooltip_text = (f"Seq: {seq}\nResend at: {resend_event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
                                    if resend_event else f"Seq: {seq}")
            else:
                tooltip_parts = []
                if self.check_vars["seq"].get():
                    tooltip_parts.append(f"Seq: {seq}")
                if self.check_vars["timestamp"].get():
                    for event in events:
                        tooltip_parts.append(f"{event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                if self.check_vars["type"].get():
                    tooltip_parts.append("Events: " + ", ".join(str(event["type"]) for event in events))
                if self.check_vars["count"].get():
                    tooltip_parts.append("Count: " + ", ".join(str(event["count"]) for event in events))
                tooltip_text = "\n".join(tooltip_parts)
            self.seq_info.append({
                "seq": seq,
                "final_state": final_state,
                "tooltip": tooltip_text,
                "events": events
            })

        # Сортируем информацию по seq (по возрастанию)
        self.seq_info.sort(key=lambda x: x["seq"])

        # Параметры для отрисовки: квадрат и зазор
        square_width = 0.8
        gap = 0.2
        y_coord = 0.5  # отрисовка на верхней половине (y от 0.5 до 1)
        for idx, info in enumerate(self.seq_info):
            color = self.colors.get(info["final_state"], "#FFFFFF")
            x = idx * (square_width + gap)
            patch = self.ax.add_patch(Rectangle((x, y_coord), square_width, 0.5, color=color))
            self.bar_patches.append(patch)

        total_seq = len(self.seq_info)
        self.ax.set_xlim(0, total_seq * (square_width + gap))
        self.ax.set_ylim(0, 1)
        self.ax.axis("off")

        # Устанавливаем xticks по центру каждого квадрата с номерами seq
        xticks = []
        xlabels = []
        for idx, info in enumerate(self.seq_info):
            x_center = idx * (square_width + gap) + square_width / 2
            xticks.append(x_center)
            xlabels.append(str(info["seq"]))
        self.ax.set_xticks(xticks)
        self.ax.set_xticklabels(xlabels, color="white", rotation=45, fontsize=10)

        self.canvas.draw()
        # git commit -m "feat: Реализована отрисовка state timeline с разделением квадратов и подписями seq"

        self.update_summary_table()

    def update_summary_table(self):
        """
        /**
         * Вычисляет и обновляет сводную таблицу:
         *   totalReceived = количество seq с final_state 1 или 2
         *   totalLost = количество seq с final_state -1
         *   lossRatio = (totalLost / общее количество seq) * 100%
         *   RecoveryRatio = (количество seq с final_state 2 / (количество seq с final_state 2 + -1)) * 100%
         */
        """
        total_seq = len(self.seq_info)
        totalReceived = sum(1 for info in self.seq_info if info["final_state"] in [1, 2])
        totalLost = sum(1 for info in self.seq_info if info["final_state"] == -1)
        recovery_count = sum(1 for info in self.seq_info if info["final_state"] == 2)
        lossRatio = (totalLost / total_seq * 100) if total_seq > 0 else 0
        denominator = (totalLost + recovery_count)
        RecoveryRatio = (recovery_count / denominator * 100) if denominator > 0 else 0
        summary_text = (f"Total Received: {totalReceived}\n"
                        f"Total Lost: {totalLost}\n"
                        f"Loss Ratio: {lossRatio:.1f}%\n"
                        f"Recovery Ratio: {RecoveryRatio:.1f}%")
        if not hasattr(self, "summary_label"):
            self.summary_label = tk.Label(self.root, text=summary_text, font=self.font, bg="#2E2E2E", fg="white")
            self.summary_label.pack(side=tk.BOTTOM, pady=10)
        else:
            self.summary_label.config(text=summary_text)
        # git commit -m "feat: Добавлена сводная таблица подсчета пакетов"

    def on_hover(self, event):
        """
        /**
         * Обрабатывает событие наведения мыши: при наведении на квадрат показывается tooltip.
         */
        """
        current_time = time.time()
        if current_time - self.last_update_time < self.update_interval:
            return

        self.last_update_time = current_time

        current_patch = None
        for patch in self.bar_patches:
            if patch.contains(event)[0]:
                current_patch = patch
                break

        if current_patch == self.last_patch:
            return

        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

        self.last_patch = current_patch
        if current_patch:
            tooltip_text = self.get_tooltip_text(current_patch)
            self.show_tooltip(event, tooltip_text)
        # git commit -m "feat: Реализована логика показа tooltip при наведении на квадрат"

    def get_tooltip_text(self, patch):
        """
        /**
         * Генерирует текст для tooltip по данным seq.
         * @param patch Объект квадрата, на который наведён курсор.
         * @return Текст для tooltip.
         */
        """
        try:
            index = self.bar_patches.index(patch)
            info = self.seq_info[index]
            return info["tooltip"]
        except Exception as e:
            print(f"[ERROR] Ошибка при получении данных для tooltip: {e}")
            return "Ошибка данных"
        # git commit -m "fix: Обработка ошибок в get_tooltip_text"

    def show_tooltip(self, event, text):
        """
        /**
         * Отображает tooltip рядом с курсором.
         * @param event Событие наведения мыши.
         * @param text Текст для отображения.
         */
        """
        x_root, y_root = self.root.winfo_pointerxy()
        self.tooltip_window = tk.Toplevel(self.root)
        self.tooltip_window.wm_overrideredirect(1)
        self.tooltip_window.wm_geometry(f"+{x_root + 10}+{y_root + 10}")
        label = tk.Label(self.tooltip_window, text=text, font=self.font, bg="#333333", fg="white", relief=tk.SOLID)
        label.pack(padx=5, pady=5)
        # git commit -m "feat: Реализована функция показа tooltip"

    def remove_tooltip(self):
        """
        /**
         * Удаляет tooltip, если он отображается.
         */
        """
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
            self.last_patch = None
        # git commit -m "refactor: Добавлена функция удаления tooltip"

if __name__ == "__main__":
    root = tk.Tk()
    app = CSVGraphApp(root)
    root.mainloop()
