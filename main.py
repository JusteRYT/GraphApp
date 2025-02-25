import tkinter as tk
from tkinter import filedialog, ttk
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import time
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.patches import Rectangle

# Используем TkAgg и темную тему
matplotlib.use("TkAgg")
plt.style.use('dark_background')


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
      * Сводная таблица (в левом нижнем углу) подсчитывает:
      *   Total Received, Total Lost, Loss Ratio, Recovery Ratio.
      *
      * При запуске программы основной контейнер с графиком не отображается до загрузки CSV.
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
        self.root.update_idletasks()
        self.center_half_screen()
        self.root.configure(bg="#2E2E2E")

        self.font = ("Segoe UI", 12)
        self.button_font = ("Segoe UI", 12, "bold")

        # --- Верхняя панель: навигационная панель (toolbar) ---
        self.toolbar_frame = tk.Frame(self.root, bg="#2E2E2E")
        self.toolbar_frame.pack(side=tk.TOP, fill=tk.X)

        # --- Контрольная панель: кнопки и чекбоксы ---
        self.control_frame = tk.Frame(self.root, bg="#2E2E2E")
        self.control_frame.pack(pady=10, fill=tk.X)

        self.select_button = tk.Button(
            self.control_frame, text="Выбрать CSV файл", command=self.load_csv,
            font=self.button_font, bg="#555555", fg="white", relief=tk.FLAT
        )
        self.select_button.pack(side=tk.LEFT, padx=5)

        self.plot_button = tk.Button(
            self.control_frame, text="Построить график", command=self.plot_graph,
            state=tk.DISABLED, font=self.button_font, bg="#555555",
            fg="white", relief=tk.FLAT
        )
        self.plot_button.pack(side=tk.LEFT, padx=5)

        self.file_label = tk.Label(
            self.control_frame, text="Файл не выбран", font=self.font, bg="#2E2E2E", fg="white"
        )
        self.file_label.pack(side=tk.LEFT, padx=10)

        # Чекбоксы с соответствующими подписями
        self.create_checkboxes()

        # --- Основной контейнер с графиком и сводной таблицей ---
        self.main_frame = tk.Frame(self.root, bg="#2E2E2E")
        # Пока не отображаем main_frame до загрузки CSV

        # Фрейм для графика (занимает основную часть)
        self.graph_frame = tk.Frame(self.main_frame, bg="#2E2E2E")
        self.graph_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Фрейм для сводной таблицы (расположен в левом нижнем углу)
        self.summary_frame = tk.Frame(self.main_frame, bg="#2E2E2E")
        self.summary_frame.pack(side=tk.BOTTOM, anchor="w", fill=tk.X, padx=10, pady=10)

        # Создаем фигуру и ось для графика (начальный размер задаем как (8,4))
        self.figure, self.ax = plt.subplots(figsize=(8, 4), facecolor="#2E2E2E")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        # Панель инструментов – упаковываем в toolbar_frame (выше всех)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame, pack_toolbar=False)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # Выделение по hover реализуем через изменение обводки
        self.selected_patch = None

        self.tooltip_window = None
        self.last_patch = None
        self.update_interval = 0.1  # интервал обновления tooltip (100 мс)
        self.last_update_time = 0
        self.bar_patches = []  # список объектов-квадратов
        self.seq_info = []  # список агрегированной информации по seq

        self.data = None  # данные CSV
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

        self.colors = {
            -1: "#FF0000",  # lost – красный
            1: "#00FF00",   # received – зеленый
            2: "#FFD700"    # resend – желтый
        }

    def center_half_screen(self):
        """
         /**
          * Центрирует окно, устанавливая его размер половиной экрана (но не больше 1920x1080).
          */
        """
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        # [REFAC] Убраны лишние отладочные print'ы
        width = int(screen_width * 0.5)
        height = int(screen_height * 0.5)
        max_width = 2560
        max_height = 1440
        width = min(width, max_width)
        height = min(height, max_height)
        x = int((screen_width - width) / 2)
        y = int((screen_height - height) / 2)
        geometry_str = f"{width}x{height}+{x}+{y}"
        self.root.geometry(geometry_str)

    def create_checkboxes(self):
        """
         /**
          * Создает чекбоксы для выбора информации, отображаемой в tooltip.
          */
        """
        self.check_vars = {
            "seq": tk.BooleanVar(value=True),
            "timestamp": tk.BooleanVar(value=True),
            "events": tk.BooleanVar(value=True),
            "count": tk.BooleanVar(value=True)
        }
        check_frame = tk.Frame(self.root, bg="#2E2E2E")
        check_frame.pack(fill=tk.X, padx=10)
        ttk.Checkbutton(check_frame, text="Show Seq", variable=self.check_vars["seq"], style="TCheckbutton").pack(
            side=tk.LEFT, padx=5)
        ttk.Checkbutton(check_frame, text="Show timestamp", variable=self.check_vars["timestamp"],
                        style="TCheckbutton").pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(check_frame, text="Show event", variable=self.check_vars["events"], style="TCheckbutton").pack(
            side=tk.LEFT, padx=5)
        ttk.Checkbutton(check_frame, text="Show count", variable=self.check_vars["count"], style="TCheckbutton").pack(
            side=tk.LEFT, padx=5)
        for var in self.check_vars.values():
            var.trace_add("write", lambda name, index, mode: self.update_visible_tooltip())

    def update_visible_tooltip(self):
        """Если tooltip открыт, обновляем его текст с учётом текущих настроек."""
        if self.tooltip_window and self.last_patch:
            tooltip_text = self.get_tooltip_text(self.last_patch)
            for widget in self.tooltip_window.winfo_children():
                widget.config(text=tooltip_text)

    def load_csv(self):
        """
         /**
          * Загружает CSV и проверяет наличие столбцов 'timestamp', 'seq', 'type'.
          */
        """
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        try:
            df = pd.read_csv(file_path)
            if not {"timestamp", "seq", "type"}.issubset(df.columns):
                raise ValueError("CSV не содержит столбцы: timestamp, seq, type")
            df["type"] = df["type"].astype(int)
            if "count" not in df.columns:
                df["count"] = 1
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")
            df = df.dropna(subset=["timestamp"])
            self.data = df
            self.file_label.config(text=f"Выбран файл: {file_path.split('/')[-1]}")
            self.plot_button.config(state=tk.NORMAL)
            # Отображаем основной контейнер, если он ещё не отображён
            if not self.main_frame.winfo_ismapped():
                self.main_frame.pack(fill=tk.BOTH, expand=True)
            self.plot_graph()
        except Exception as e:
            self.file_label.config(text=f"Ошибка: {e}")
            self.plot_button.config(state=tk.DISABLED)

    def plot_graph(self):
        """
         /**
          * Строит state timeline:
          * - Группирует данные по 'seq' и определяет итоговое состояние.
          * - Если final_state == 2, tooltip показывает только время потери и восстановления.
          * - Отрисовывает квадраты (размер 1x1) с зазором по оси X, устанавливает xticks (без поворота).
          * - Сводная таблица выводится в summary_frame.
          * - Размер фигуры обновляется динамически, чтобы показать все элементы.
          */
        """
        if self.data is None or self.data.empty:
            return

        self.ax.clear()
        self.bar_patches.clear()
        self.seq_info.clear()

        grouped = self.data.groupby("seq")
        for seq, group in grouped:
            group = group.sort_values("timestamp")
            events = group.to_dict('records')
            types = group["type"].tolist()
            if 2 in types:
                final_state = 2
            elif 1 in types:
                final_state = 1
            elif -1 in types:
                final_state = -1
            else:
                final_state = -1

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
                tooltip_text = None
            self.seq_info.append({
                "seq": seq,
                "final_state": final_state,
                "events": events
            })

        self.seq_info.sort(key=lambda x: x["seq"])

        square_width = 0.8
        gap = 0.2
        y_coord = 0.5
        for idx, info in enumerate(self.seq_info):
            color = self.colors.get(info["final_state"], "#FFFFFF")
            x = idx * (square_width + gap)
            patch = self.ax.add_patch(Rectangle((x, y_coord), square_width, 0.5, color=color))
            self.bar_patches.append(patch)

        total_seq = len(self.seq_info)
        self.ax.set_xlim(0, total_seq * (square_width + gap))
        self.ax.set_ylim(0, 1)
        self.ax.get_yaxis().set_visible(False)
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["left"].set_visible(False)
        self.ax.spines["right"].set_visible(False)

        xticks = []
        xlabels = []
        for idx, info in enumerate(self.seq_info):
            x_center = idx * (square_width + gap) + square_width / 2
            xticks.append(x_center)
            xlabels.append(str(info["seq"]))
        self.ax.set_xticks(xticks)
        self.ax.set_xticklabels(xlabels, color="white", rotation=0, fontsize=10)

        # Переопределяем формат отображения координат в панели инструментов
        def format_coord(x, y):
            idx = int(x // (square_width + gap))
            if 0 <= idx < len(self.seq_info):
                seq = self.seq_info[idx]["seq"]
                return f"x={x:.2f}, y={y:.2f}, seq={seq}"
            else:
                return f"x={x:.2f}, y={y:.2f}"
        self.ax.format_coord = format_coord

        new_width = max(8, int(total_seq * (square_width + gap)))
        self.figure.set_size_inches(new_width, 4, forward=True)
        self.canvas.draw()

        self.update_summary_table()

    def update_summary_table(self):
        """
         /**
          * Вычисляет и обновляет сводную таблицу подсчёта.
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
            self.summary_label = tk.Label(self.summary_frame, text=summary_text, font=self.font,
                                          bg="#2E2E2E", fg="white", bd=1, relief=tk.SOLID, padx=5, pady=5)
            self.summary_label.pack(side=tk.LEFT, anchor="w", padx=5, pady=5)
        else:
            self.summary_label.config(text=summary_text)
        # git commit -m "feat: Обновлена сводная таблица, размещена в левом нижнем углу"

    def get_tooltip_text(self, patch):
        """
         /**
          * Вычисляет текст tooltip динамически на основе текущих значений чекбоксов.
          */
        """
        try:
            index = self.bar_patches.index(patch)
            info = self.seq_info[index]
            seq = info["seq"]
            events = info["events"]
            final_state = info["final_state"]
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
                    # Для каждого события типа 1 добавляем префикс "timestamp:"
                    for event in events:
                        formatted_time = event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                        if event["type"] == 1:
                            tooltip_parts.append("Timestamp: " + formatted_time)
                        else:
                            tooltip_parts.append(formatted_time)
                if self.check_vars["events"].get():
                    # Маппинг для вывода событий: -1 -> lost, 1 -> recieved, 2 -> resend
                    mapping = {-1: "Lost", 1: "Received", 2: "Resend"}
                    tooltip_parts.append("Events: " + ", ".join(mapping.get(event["type"], str(event["type"])) for event in events))
                if self.check_vars["count"].get():
                    tooltip_parts.append("Count: " + ", ".join(str(event["count"]) for event in events))
                tooltip_text = "\n".join(tooltip_parts)
            return tooltip_text
        except Exception as e:
            print(f"[ERROR] Ошибка при получении данных для tooltip: {e}")
            return "Ошибка данных"
        # git commit -m "fix: Обновлена функция get_tooltip_text для вывода timestamp и events по требованиям"

    def on_hover(self, event):
        """
         /**
          * При наведении на квадрат отображается tooltip и выделяется квадрат.
          * Если мышь не над ни одним patch, tooltip удаляется.
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

        # Если мышь не над ни одним patch, убираем tooltip и сбрасываем выделение
        if current_patch is None:
            if self.tooltip_window:
                self.tooltip_window.destroy()
                self.tooltip_window = None
            if self.last_patch:
                self.last_patch.set_linewidth(0)
                self.last_patch.set_edgecolor(None)
                self.last_patch = None
            self.canvas.draw_idle()
            return

        if current_patch != self.last_patch:
            if self.last_patch is not None:
                self.last_patch.set_linewidth(0)
                self.last_patch.set_edgecolor(None)
            self.last_patch = current_patch
            current_patch.set_linewidth(3)
            current_patch.set_edgecolor("white")
            self.canvas.draw_idle()
            tooltip_text = self.get_tooltip_text(current_patch)
            self.show_tooltip(event, tooltip_text)

    def show_tooltip(self, event, text):
        """
         /**
          * Отображает tooltip рядом с курсором.
          */
        """
        x_root, y_root = self.root.winfo_pointerxy()
        if self.tooltip_window:
            self.tooltip_window.destroy()
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
