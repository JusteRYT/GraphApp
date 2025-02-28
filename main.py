import math
import os
import tkinter as tk
from tkinter import filedialog, ttk
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import time
import ast
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.collections import PatchCollection

# Используем TkAgg и темную тему
matplotlib.use("TkAgg")
plt.style.use('dark_background')


def _format_final_state_2(seq, events):
    """
     /**
      * Форматирует tooltip для final_state == 2.
      * Находит первый event с type=2 и последний event с type=-1, предшествующий ему.
      * @param seq Значение seq.
      * @param events Список событий.
      * @return Отформатированный текст tooltip.
      */
    """
    resend_event = None
    lost_event = None
    for event in events:
        if event["type"] == 2:
            resend_event = event
            break
        elif event["type"] == -1:
            lost_event = event
    if lost_event is not None and resend_event is not None:
        return (f"Seq: {seq}\n"
                f"Lost: {lost_event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Recovered: {resend_event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
    elif resend_event is not None:
        return f"Seq: {seq}\nResend at: {resend_event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        return f"Seq: {seq}"


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

    def __init__(self, master):
        """
         /**
          * Конструктор класса.
          * @param master Корневое окно Tkinter.
          */
        """
        self.root = master
        self.root.title("State Timeline из CSV")
        self.root.update_idletasks()
        self.center_half_screen()
        self.root.configure(bg="#2E2E2E")

        self.font = ("Segoe UI", 12)
        self.button_font = ("Segoe UI", 12, "bold")

        # Инициализация атрибутов для избежания предупреждений
        self.check_vars = {}
        self.summary_label = None

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

        # Чекбоксы для отображения информации в tooltip
        self.create_checkboxes()

        # --- Основной контейнер с графиком и сводной таблицей ---
        self.main_frame = tk.Frame(self.root, bg="#2E2E2E")
        # Отображаем main_frame только после загрузки CSV

        # Фрейм для графика
        self.graph_frame = tk.Frame(self.main_frame, bg="#2E2E2E")
        self.graph_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Фрейм для сводной таблицы
        self.summary_frame = tk.Frame(self.main_frame, bg="#2E2E2E")
        self.summary_frame.pack(side=tk.BOTTOM, anchor="w", fill=tk.X, padx=10, pady=10)

        # Создаем фигуру и ось для графика
        self.figure, self.ax = plt.subplots(figsize=(8, 4), facecolor="#2E2E2E")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        # Панель инструментов
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame, pack_toolbar=False)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # Выделение при hover
        self.selected_patch = None
        self._facecolors = {}

        self.tooltip_window = None
        self.last_patch = None
        self.update_interval = 0.1  # 100 мс
        self.last_update_time = 0
        self.bar_patches = []  # список квадратов
        self.norm_tooltips = []
        self.norm_collection = []
        self.nack_tooltips = []
        self.nack_collection = []
        self.nack_box_tooltips = []
        self.frame_collection = []
        self.frame_tooltips = []
        self.nack_rects = []
        self.frame_rects = []
        self.seq_info: dict = {}  # агрегированная информация по seq
        self.generated_color = 'lime'
        self.ungenerated_color = 'orangered'

        self.data = None  # данные CSV
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

        self.colors = {
            -1: "#FF0000",  # lost – красный
            1: "#00FF00",  # received – зеленый
            2: "#FFD700"  # resend – желтый
        }

        # Оптимизация отрисовки
        self.square_width = 0.8
        self.gap = 0.2

    def center_half_screen(self):
        """
         /**
          * Центрирует окно, устанавливая его размер половиной экрана (но не больше 1920x1080).
          */
        """
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = int(screen_width)
        height = int(screen_height)
        max_width = 2560
        max_height = 1440
        width = min(width, max_width)
        height = int((height + max_height) / 2)
        x = int((screen_width - width) / 5.2)
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
        """Если tooltip открыт, обновляем его текст с учётом настроек."""
        if not self.tooltip_window or not self.last_patch:
            return

        tooltip_text = "Нет данных"

        # Проверяем, в какой коллекции находится patch
        if self.norm_collection and self.last_patch in self.norm_collection.get_paths():
            idx = self.norm_collection.get_paths().index(self.last_patch)
            tooltip_text = self.norm_tooltips[idx] if idx < len(self.norm_tooltips) else "Нет данных"

        elif self.nack_collection and self.last_patch in self.nack_collection.get_paths():
            idx = self.nack_collection.get_paths().index(self.last_patch)
            tooltip_text = self.nack_tooltips[idx] if idx < len(self.nack_tooltips) else "Нет данных"

        elif self.frame_collection and self.last_patch in self.frame_collection.get_paths():
            idx = self.frame_collection.get_paths().index(self.last_patch)
            tooltip_text = self.frame_tooltips[idx] if idx < len(self.frame_tooltips) else "Нет данных"

        # Обновляем текст tooltip'а
        for widget in self.tooltip_window.winfo_children():
            widget.config(text=tooltip_text)

    @staticmethod
    def parse_seq(row):
        """
        Парсит значение столбца 'seq'. Если row["type"] == 3, ожидается строка в формате "[9, 19, 29]"
        и возвращается список чисел. Для остальных типов, если значение выглядит как список,
        берётся первый элемент, иначе – пытается преобразовать значение к int.
        Добавлены отладочные сообщения для отслеживания ошибок преобразования.
        """
        if pd.isna(row["seq"]):
            print(f"[DEBUG] Отсутствует значение 'seq' для строки с timestamp {row.get('timestamp')}")
            return []

        seq_val = row["seq"]
        # Если значение представлено строкой
        if isinstance(seq_val, str):
            seq_val = seq_val.strip()
            # Если строка выглядит как список
            if seq_val.startswith("[") and seq_val.endswith("]"):
                try:
                    parsed = ast.literal_eval(seq_val)
                except Exception as e:
                    print(f"[DEBUG] Ошибка при парсинге строки 'seq' {seq_val}: {e}")
                    return []
                if row["type"] != 3.0:
                    # Для обычных событий берём первый элемент списка
                    if parsed:
                        first_elem = parsed[0]
                        if pd.isna(first_elem) or (isinstance(first_elem, (int, float)) and (math.isinf(first_elem))):
                            print(f"[DEBUG] Невалидное число {first_elem} в строке {seq_val}")
                            return []
                        try:
                            return [int(first_elem)]
                        except Exception as e:
                            print(f"[DEBUG] Ошибка преобразования первого элемента {first_elem} в int: {e}")
                            return []
                    else:
                        return []
                else:
                    # Для nack (type==3) возвращаем весь список
                    return parsed
            else:
                try:
                    val = int(seq_val)
                    return [val]
                except Exception as e:
                    print(f"[DEBUG] Ошибка преобразования 'seq' '{seq_val}' в int: {e}")
                    return []
        # Если значение уже является списком
        elif isinstance(seq_val, list):
            if row["type"] != 3:
                if seq_val:
                    first_elem = seq_val[0]
                    if pd.isna(first_elem) or (isinstance(first_elem, (int, float)) and math.isinf(first_elem)):
                        print(f"[DEBUG] Невалидное число {first_elem} в списке {seq_val}")
                        return []
                    try:
                        return [int(first_elem)]
                    except Exception as e:
                        print(f"[DEBUG] Ошибка преобразования первого элемента списка {seq_val} в int: {e}")
                        return []
                else:
                    return []
            else:
                return seq_val
        else:
            try:
                val = int(seq_val)
                return [val]
            except Exception as e:
                print(f"[DEBUG] Ошибка преобразования 'seq' {seq_val} в int: {e}")
                return []

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
            df["seq_list"] = df.apply(CSVGraphApp.parse_seq, axis=1)
            if not {"timestamp", "seq", "type"}.issubset(df.columns):
                raise ValueError("CSV не содержит столбцы: timestamp, seq, type")
            df["type"] = df["type"].astype(float)
            if "count" not in df.columns:
                df["count"] = 1
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")
            df = df.dropna(subset=["timestamp"])
            self.data = df
            # Проверяем, что файл file_path - строка
            if isinstance(file_path, str):
                filename = os.path.basename(file_path)
                self.file_label.config(text=f"Выбран файл: {filename}")
            else:
                self.file_label.config(text="Ошибка: Некорректный путь к файлу")
            self.plot_button.config(state=tk.NORMAL)
            # Отображаем основной контейнер, если он ещё не показан
            if not self.main_frame.winfo_ismapped():
                self.main_frame.pack(fill=tk.BOTH, expand=True)
            self.plot_graph()
        except Exception as e:
            self.file_label.config(text=f"Ошибка: {e}")
            self.plot_button.config(state=tk.DISABLED)

    def plot_graph(self):
        """
         1) Собирает все уникальные seq (из всех строк, независимо от type).
         2) Отрисовывает нормальные события (type != 3) на y=0.5.
         3) Для nack (type == 3) рисует тонкие прямоугольники снизу, ближе к bar_patch:
            - Если нет пересечения по seq, располагается на «нулевой» линии (base_y - 0.2).
            - Если пересекается, сдвигается на линию ниже (line_spacing).
            - Внутри прямоугольника рисуются точки по центру.
         4) Рисует состояние фрейма (блоки по 10 seq).
         5) Настраивает оси, масштаб и обновляет сводную таблицу.
        """
        from matplotlib.patches import Rectangle
        from matplotlib.collections import PatchCollection

        if self.data is None or self.data.empty:
            return

        # 1. Очистка предыдущего графика
        self.ax.clear()

        # Собираем все seq из seq_list
        all_seq = set()
        for _, row in self.data.iterrows():
            for s in row["seq_list"]:
                all_seq.add(s)
        sorted_seq = sorted(all_seq)
        seq_to_index = {seq: i for i, seq in enumerate(sorted_seq)}

        # Отрисовываем прямоугольники для нормальных событий
        square_width = 0.8
        gap = 0.2
        base_y = 0.5

        # 2. Нормальные события (type != 3)
        normal_df = self.data[self.data["type"] != 3]
        seq_info_dict = {}
        for seq in sorted_seq:
            # Выбираем все строки из normal_df, где seq содержится в seq_list
            group = normal_df[normal_df["seq_list"].apply(lambda lst: seq in lst)]
            events = group.sort_values("timestamp").to_dict('records')
            types = group["type"].tolist()
            if 2 in types:
                final_state = 2
            elif 1 in types:
                final_state = 1
            elif -1 in types:
                final_state = -1
            else:
                final_state = -1
            self.seq_info[seq] = {"final_state": final_state, "events": events}

        norm_rects = []
        norm_colors = []
        self.norm_tooltips = []
        for seq, data in self.seq_info.items():
            idx = seq_to_index.get(seq)
            if idx is None:
                continue
            x_coord = idx * (square_width + gap)
            norm_rects.append(Rectangle((x_coord, base_y), square_width, 0.5))
            norm_colors.append(self.colors.get(data["final_state"], "#FFFFFF"))
            self.norm_tooltips.append(self.get_tooltip_text(seq))

        self.norm_collection = PatchCollection(norm_rects, facecolors=norm_colors, edgecolors='none', picker=True)
        self.ax.add_collection(self.norm_collection)

        # 3. Nack-события (type == 3)
        # Здесь мы будем собирать nack-боксы в список и точки в отдельные массивы.
        nack_boxes = []
        self.nack_box_tooltips = []
        nack_points_x = []
        nack_points_y = []

        # Для размещения nack-боксов используем "линии": если интервалы (по индексам) пересекаются, сдвигаемся вниз.
        lines = []

        def intervals_overlap(a1, b1, a2, b2):
            return not (b1 < a2 or a1 > b2)

        # Параметры nack-боксов
        rect_height = 0.07  # тонкий прямоугольник
        line_spacing = 0.05  # вертикальный отступ между линиями, если пересекаются
        first_line_offset = 0.075  # отступ первой nack-линии от base_y

        for _, row in self.data[self.data["type"] == 3].iterrows():
            seq_list = row["seq_list"]
            if not seq_list:
                continue
            min_seq = min(seq_list)
            max_seq = max(seq_list)
            min_idx = seq_to_index.get(min_seq)
            max_idx = seq_to_index.get(max_seq)
            if min_idx is None or max_idx is None:
                continue
            start_interval = min_idx
            end_interval = max_idx
            line_index = None
            for i, intervals in enumerate(lines):
                if all(not intervals_overlap(start_interval, end_interval, a, b) for (a, b) in intervals):
                    line_index = i
                    intervals.append((start_interval, end_interval))
                    break
            if line_index is None:
                line_index = len(lines)
                lines.append([(start_interval, end_interval)])
            x_start = min_idx * (self.square_width + self.gap)
            x_end = max_idx * (self.square_width + self.gap) + self.square_width
            width_rect = x_end - x_start
            rect_y = base_y - first_line_offset - line_index * (rect_height + line_spacing)
            box = Rectangle((x_start, rect_y), width_rect, rect_height)
            box.tooltip = f"NACK: {seq_list}"
            nack_boxes.append(box)
            self.nack_box_tooltips.append(box.tooltip)
            # Для каждой seq из seq_list, точки располагаются по центру соответствующего столбца
            for s in seq_list:
                idx = seq_to_index.get(s)
                if idx is None:
                    continue
                x_center = idx * (square_width + gap) + square_width / 2
                y_center = rect_y + rect_height / 2
                nack_points_x.append(x_center)
                nack_points_y.append(y_center)

        if nack_boxes:
            self.nack_collection = PatchCollection(nack_boxes, facecolors="cyan", alpha=0.7, edgecolor="none",
                                                   picker=True)
            self.ax.add_collection(self.nack_collection)
        else:
            self.nack_collection = None

        if nack_points_x and nack_points_y:
            self.ax.scatter(nack_points_x, nack_points_y, s=25, marker="o", color="red", zorder=3)

        # 4. Состояние фрейма по блокам 10 seq
        block_size = 10
        frame_boxes = []
        self.frame_tooltips = []
        for i in range(0, len(sorted_seq), block_size):
            block = sorted_seq[i:i + block_size]
            block_state = "Generated"
            block_color = self.generated_color
            for s in block:
                if s in self.seq_info and self.seq_info[s]["final_state"] == -1:
                    block_state = "UnGenerated"
                    block_color = self.ungenerated_color
                    break
            start_idx = i
            block_width = len(block) * (self.square_width + self.gap)
            x_start = start_idx * (self.square_width + self.gap)
            box = Rectangle((x_start, 1.1), block_width, 0.2, color=block_color, alpha=0.5, zorder=1)
            box.tooltip = f"Frame: {block_state} ({block[0]} - {block[-1]})"
            frame_boxes.append(box)
            self.frame_tooltips.append(box.tooltip)
            self.ax.text(x_start + block_width / 2, 1.2, f"Frame: {block_state}", color="white",
                         fontsize=10, ha="center", va="center", zorder=2)

        if frame_boxes:
            self.frame_collection = PatchCollection(frame_boxes,
                                                    facecolors=[(
                                                                    self.generated_color if "Generated" in t else self.ungenerated_color)
                                                                for t in
                                                                self.frame_tooltips], alpha=0.5, edgecolor="none",
                                                    picker=True)
            self.ax.add_collection(self.frame_collection)
        else:
            self.frame_collection = None

        # 5. Настраиваем оси
        total_seq = len(sorted_seq)
        total_width = total_seq * (self.square_width + self.gap)

        line_count = len(lines)
        if line_count > 0:
            # самая последняя линия: line_count-1
            last_line_y = base_y - first_line_offset - (line_count - 1) * (rect_height + line_spacing)
            # небольшой запас снизу
            y_min = last_line_y - 0.3
        else:
            y_min = 0

        self.ax.set_xlim(0, total_width)
        self.ax.set_ylim(y_min, 1.5)
        self.ax.get_yaxis().set_visible(False)
        for spine in ["top", "left", "right"]:
            self.ax.spines[spine].set_visible(False)

        # xticks и xlabels
        xticks = [i * (square_width + gap) + square_width / 2 for i in range(total_seq)]
        xlabels = [str(seq) for seq in sorted_seq]
        self.ax.set_xticks(xticks)
        self.ax.set_xticklabels(xlabels, color="white", fontsize=12, rotation=90)

        def format_coord(x_val, _y_val):
            i_index = int(x_val // (square_width + gap))
            if 0 <= i_index < len(sorted_seq):
                return f"seq={sorted_seq[i_index]}"
            else:
                return ""

        self.ax.format_coord = format_coord

        width_inches = max(8, math.ceil(total_width))
        self.figure.set_size_inches(width_inches, 4, forward=True)
        self.canvas.draw()

        # 6. Обновляем сводную таблицу
        self.update_summary_table()

    def update_summary_table(self):
        """
         /**
          * Вычисляет и обновляет сводную таблицу подсчёта.
          */
        """
        total_seq = len(self.seq_info)
        total_received = sum(1 for info in self.seq_info.values() if info["final_state"] in [1, 2])
        total_lost = sum(1 for info in self.seq_info.values() if info["final_state"] == -1)
        recovery_count = sum(1 for info in self.seq_info.values() if info["final_state"] == 2)
        loss_ratio = (total_lost / total_seq * 100) if total_seq > 0 else 0
        denominator = (total_lost + recovery_count)
        recovery_ratio = (recovery_count / denominator * 100) if denominator > 0 else 0
        summary_text = (f"Total Received: {total_received}\n"
                        f"Total Lost: {total_lost}\n"
                        f"Loss Ratio: {loss_ratio:.1f}%\n"
                        f"Recovery Ratio: {recovery_ratio:.1f}%")
        if self.summary_label is None:
            self.summary_label = tk.Label(self.summary_frame, text=summary_text, font=self.font,
                                          bg="#2E2E2E", fg="white", bd=1, relief=tk.SOLID, padx=5, pady=5)
            self.summary_label.pack(side=tk.LEFT, anchor="w", padx=5, pady=5)
        else:
            self.summary_label.config(text=summary_text)

    def get_tooltip_text(self, seq):
        """
        Возвращает текст tooltip для конкретного seq.
        """
        if seq not in self.seq_info:
            return "Нет данных для tooltip"

        info = self.seq_info[seq]
        events = info["events"]
        final_state = info["final_state"]

        tooltip_parts = []

        if final_state == 2:
            return _format_final_state_2(seq, events)

        if self.check_vars["seq"].get():
            tooltip_parts.append(f"Seq: {seq}")

        if self.check_vars["timestamp"].get():
            timestamps = []
            for event in events:
                formatted_time = event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                if event["type"] in (1.0, -1.0):
                    timestamps.append("Timestamp: " + formatted_time)
                else:
                    timestamps.append(formatted_time)
            tooltip_parts.append("\n".join(timestamps))

        if self.check_vars["events"].get():
            mapping = {-1.0: "Lost", 1.0: "Received", 2.0: "Resend"}
            event_types = [mapping.get(event["type"], str(event["type"])) for event in events if
                           not pd.isna(event["type"])]
            tooltip_parts.append("Events: " + ", ".join(event_types))

        if self.check_vars["count"].get():
            counts = [str(event["count"]) for event in events]
            tooltip_parts.append("Count: " + ", ".join(counts))

        return "\n".join(tooltip_parts)

    def on_hover(self, event):
        current_time = time.time()
        if current_time - self.last_update_time < self.update_interval:
            return
        self.last_update_time = current_time

        # Объединяем все патчи, для которых хотим показывать tooltip
        all_patches = self.bar_patches + getattr(self, "nack_rects", []) + getattr(self, "frame_rects", [])
        current_patch = None
        for patch in all_patches:
            contains, _ = patch.contains(event)
            if contains:
                current_patch = patch
                break

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
            # Выделяем только нормальные события (bar_patches)
            if current_patch in self.bar_patches:
                current_patch.set_linewidth(3)
                current_patch.set_edgecolor("white")
            self.canvas.draw_idle()

            # Если у патча уже задан tooltip (для nack и frame), используем его,
            # иначе вызываем get_tooltip_text для обычного bar_patch
            if hasattr(current_patch, "tooltip"):
                tooltip_text = current_patch.tooltip
            else:
                tooltip_text = self.get_tooltip_text(current_patch)
            self.show_tooltip(tooltip_text)

    def show_tooltip(self, text):
        """
         /**
          * Отображает tooltip рядом с курсором.
          */
        """
        x_root, y_root = self.root.winfo_pointerxy()
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = tk.Toplevel(self.root)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x_root + 10}+{y_root + 10}")
        label = tk.Label(self.tooltip_window, text=text, font=self.font, bg="#333333", fg="white", relief=tk.SOLID)
        label.pack(padx=5, pady=5)

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


if __name__ == "__main__":
    root = tk.Tk()
    app = CSVGraphApp(root)
    root.mainloop()
