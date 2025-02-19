import tkinter as tk
from tkinter import filedialog, ttk
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.patches import FancyBboxPatch
from matplotlib.dates import DateFormatter

# Используем TkAgg
matplotlib.use("TkAgg")
plt.style.use('dark_background')


class CSVGraphApp:
    """
    Приложение для чтения CSV и построения многослойной гистограммы.
    Для каждого (timestamp, seq) рисуется отдельный столбец с вложенными слоями по type:
      - type = -1 (lost) – красный (коэффициент 0.4)
      - type = 2 (resend) – желтый (коэффициент 0.6)
      - type = 1 (received) – зеленый (коэффициент 1.0)
    Если для одного timestamp несколько seq – столбики в кластере разделяются небольшим зазором.
    При наведении на столбик появляется tooltip рядом с курсором.
    Окно центрируется и ограничено по размерам.
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Просмотр графиков из CSV")
        self.root.update_idletasks()  # гарантирует получение актуальных размеров экрана
        self.center_half_screen()
        self.root.configure(bg="#2E2E2E")

        self.font = ("Segoe UI", 12)
        self.button_font = ("Segoe UI", 12, "bold")

        # Фрейм для кнопок
        control_frame = tk.Frame(root, bg="#2E2E2E")
        control_frame.pack(pady=10, fill=tk.X)

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

        # Мы не используем фиксированную метку для tooltip,
        # так как реализуем всплывающее окно
        self.tooltip_window = None

        # Область для графика
        self.figure, self.ax = plt.subplots(figsize=(8, 4), facecolor="#2E2E2E")
        self.canvas = FigureCanvasTkAgg(self.figure, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.toolbar = NavigationToolbar2Tk(self.canvas, root, pack_toolbar=False)
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.toolbar.configure(bg="#404040")
        for child in self.toolbar.winfo_children():
            if isinstance(child, tk.Button):
                child.config(bg="#555555")
            elif isinstance(child, tk.Label):
                child.config(bg="#404040")

        self.data = None
        self.bar_patches = []  # для хранения данных столбиков (для tooltip)
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

        # Коэффициенты для высоты столбика по типу
        self.type_heights = {
            -1: 0.4,  # lost
            2: 0.6,  # resend
            1: 1.0  # received
        }
        # Цвета для типов
        self.colors = {
            -1: "#FF0000",  # красный
            2: "#FFD700",  # желтый
            1: "#00FF00"  # зеленый
        }

    def center_half_screen(self):
        """Центрирует окно, делая его размером половина экрана, но не превышая максимум (1280x720)."""
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

    def create_checkboxes(self):
        """Создаёт чекбоксы для выбора информации, отображаемой в tooltip."""
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

    def load_csv(self):
        """Загружает CSV-файл и проверяет наличие столбцов 'timestamp', 'seq', 'type'."""
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
            self.data = df
            self.file_label.config(text=f"Выбран файл: {file_path.split('/')[-1]}")
            self.plot_button.config(state=tk.NORMAL)
            print(f"[INFO] Загружено {len(self.data)} строк. Пример:\n{self.data.head()}", flush=True)
            print(f"[DEBUG] Количество строк в self.data после загрузки: {len(self.data)}", flush=True)
            self.plot_graph()
        except Exception as e:
            print(f"[ERROR] Ошибка при загрузке CSV: {e}", flush=True)
            self.file_label.config(text=f"Ошибка: {e}")
            self.plot_button.config(state=tk.DISABLED)

    def plot_graph(self):
        """
        Строит график:
         - Преобразует timestamp в datetime.
         - Группирует данные по (timestamp, seq, type) и суммирует count.
         - Для каждого (timestamp, seq) рисует столбец с вложенными слоями по type.
         - Вычисляет координаты центра для меток оси X.
        """
        if self.data is None:
            print("[WARN] Данные не загружены, прерываем построение графика.", flush=True)
            return

        try:
            print("[INFO] Строим график...", flush=True)
            self.ax.clear()
            self.bar_patches.clear()

            # Преобразуем timestamp
            self.data["timestamp"] = pd.to_datetime(self.data["timestamp"].astype(int), unit="s", errors="coerce")
            self.data = self.data.dropna(subset=["timestamp"])

            # Группируем по (timestamp, seq, type)
            grouped = self.data.groupby(["timestamp", "seq", "type"], as_index=False)["count"].sum()
            if len(grouped) == 0:
                raise ValueError("После группировки (timestamp, seq, type) нет данных.")
            grouped = grouped.sort_values(["timestamp", "seq"])

            # Формируем словарь: { timestamp: { seq: { type: count } } }
            ts_dict = {}
            for _, row in grouped.iterrows():
                ts = row["timestamp"]
                sq = row["seq"]
                tp = row["type"]
                cnt = row["count"]
                if ts not in ts_dict:
                    ts_dict[ts] = {}
                if sq not in ts_dict[ts]:
                    ts_dict[ts][sq] = {}
                if tp not in ts_dict[ts][sq]:
                    ts_dict[ts][sq][tp] = 0
                ts_dict[ts][sq][tp] += cnt

            # Для оси X: списки центров столбиков и меток
            bar_centers = []
            bar_labels = []
            cluster_width = 1.0  # ширина кластера для одного timestamp
            gap_between_bars = 0.2  # зазор между столбиками внутри кластера
            gap_between_clusters = 0.5  # зазор между кластерами (timestamp)

            def get_bar_width(n):
                return (cluster_width - (n - 1) * gap_between_bars) / (n + 1) if n > 1 else cluster_width

            # Вычисляем координаты для всех столбиков
            timestamps_unique = sorted(ts_dict.keys())
            for idx, ts in enumerate(timestamps_unique):
                seq_dict = ts_dict[ts]
                seqs = sorted(seq_dict.keys())
                bar_labels.append(ts.strftime('%Y-%m-%d %H:%M:%S'))
                bar_width = get_bar_width(len(seqs))
                bar_start = idx * (cluster_width + gap_between_clusters)
                for seq_idx, seq in enumerate(seqs):
                    stacked_heights = 0
                    for tp in [1, 2, -1]:
                        if tp in seq_dict[seq]:
                            height = seq_dict[seq][tp] * self.type_heights[tp]
                            # Добавляем столбик на график
                            bar_patch = self.ax.bar(bar_start + seq_idx * (bar_width + gap_between_bars), height, width=bar_width,
                                                    color=self.colors[tp], align='center')
                            self.bar_patches.append(bar_patch[0])

                            self.ax.bar(bar_start + seq_idx * (bar_width + gap_between_bars), height, width=bar_width,
                                        color=self.colors[tp], align="center")
                            stacked_heights += height

                    bar_centers.append(bar_start + seq_idx * (bar_width + gap_between_bars))

            # Устанавливаем метки оси X на уникальные timestamps
            if len(bar_centers) != len(bar_labels):
                print("[ERROR] Количество центров столбиков не совпадает с количеством меток оси X!", flush=True)
            else:
                self.ax.set_xticks(bar_centers)
                self.ax.set_xticklabels(bar_labels, rotation=45, color="white")

            # Устанавливаем формат отображаемых меток оси X
            date_format = DateFormatter('%Y-%m-%d %H:%M:%S')
            self.ax.xaxis.set_major_formatter(date_format)

            self.ax.set_ylabel("asix_y")
            self.ax.set_xlabel("Время")
            self.ax.grid(True, color="gray", linestyle='-', linewidth=0.5)

            self.canvas.draw()

        except Exception as e:
            print(f"[ERROR] Ошибка при построении графика: {e}", flush=True)

    def on_hover(self, event):
        """Обрабатывает событие hover (наведение на столбик)."""
        if event.inaxes != self.ax:
            return
        if self.tooltip_window:
            self.tooltip_window.destroy()
        for patch in self.bar_patches:
            if patch.contains(event)[0]:
                tooltip_text = self.get_tooltip_text(patch)
                self.show_tooltip(event, tooltip_text)
                break

    def get_tooltip_text(self, patch):
        """Генерирует текст для tooltip."""
        try:
            # Получаем строку лейбла и разбиваем её
            ts, seq, tp = patch.get_label().split("_")

            # Проверяем, что ts не пустое и можно преобразовать в int
            if ts and ts.isdigit():
                ts = pd.to_datetime(int(ts), unit="s").strftime('%Y-%m-%d %H:%M:%S')
            else:
                ts = "Неизвестно"

            tooltip_parts = []
            for key, var in self.check_vars.items():
                if var.get():
                    if key == "timestamp":
                        tooltip_parts.append(f"Timestamp: {ts}")
                    elif key == "seq":
                        tooltip_parts.append(f"Seq: {seq}")
                    elif key == "type":
                        tooltip_parts.append(f"Type: {tp}")
                    elif key == "count":
                        tooltip_parts.append(f"Count: {patch.get_height()}")

            return "\n".join(tooltip_parts)

        except Exception as e:
            print(f"[ERROR] Ошибка при формировании tooltip: {e}", flush=True)
            return "Ошибка при формировании tooltip"

    def show_tooltip(self, event, text):
        """Отображает tooltip рядом с курсором."""
        # Получаем координаты курсора относительно экрана
        x_root, y_root = self.root.winfo_pointerxy()  # Получаем координаты курсора на экране

        # Создаем окно для tooltip
        self.tooltip_window = tk.Toplevel(self.root)
        self.tooltip_window.wm_overrideredirect(1)  # Окно без рамки
        self.tooltip_window.wm_geometry(f"+{x_root + 10}+{y_root + 10}")  # Смещаем на 10 пикселей от курсора

        # Создаем метку внутри tooltip
        label = tk.Label(self.tooltip_window, text=text, font=self.font, bg="#333333", fg="white", relief=tk.SOLID)
        label.pack(padx=5, pady=5)


if __name__ == "__main__":
    root = tk.Tk()
    app = CSVGraphApp(root)
    root.mainloop()
