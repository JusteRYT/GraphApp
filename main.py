import os
import time
import tkinter as tk
import numpy as np
from tkinter import filedialog, ttk
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import ast
from typing import Any
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.collections import PatchCollection

from detailProfile import profile_detailed
from showProfile import profile_time

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

    def format_timestamp(event_value):
        """Форматирует timestamp с миллисекундами."""
        formatted_time = event_value['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        milliseconds = int(event_value['timestamp'].microsecond / 1000)
        return f"{formatted_time}:{milliseconds:03d}"

    if lost_event is not None and resend_event is not None:
        return (f"Seq: {seq}\n"
                f"Lost: {format_timestamp(lost_event)}\n"
                f"Recovered: {format_timestamp(resend_event)}")
    elif resend_event is not None:
        return f"Seq: {seq}\nResend at: {format_timestamp(resend_event)}"
    else:
        return f"Seq: {seq}"


def get_system_timezone():
    """
    Пытается определить часовой пояс системы, используя /etc/localtime.
    """
    try:
        localtime_path = os.readlink("/etc/localtime")
        parts = localtime_path.split("/")
        if len(parts) > 4 and parts[1] == "usr" and parts[2] == "share" and parts[3] == "zoneinfo":
            return "/".join(parts[4:])  # Area/Location
    except OSError:
        pass  # Файл /etc/localtime не является символической ссылкой

    return None  # Не удалось определить часовой пояс


def intervals_overlap(a1, b1, a2, b2):
    """Проверяет, перекрываются ли два интервала"""
    return not (b1 < a2 or a1 > b2)


class CSVGraphApp:
    """
    CSVGraphApp – отображает state timeline из CSV.
    Для каждого seq создаётся патч, цвет которого определяется итоговым состоянием:
      - type = -1 → красный,
      - type = 1  → зеленый,
      - type = 2  → желтый.
    Tooltip для final_state == 2 формируется особым образом.
    Дополнительно реализован lazy rendering с элементами управления для перемещения по графику.
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

        # Панель слайдера и стрелок для навигации по графику
        self.nav_frame = tk.Frame(self.root, bg="#2E2E2E")
        self.nav_frame.pack(fill=tk.BOTH, padx=10, pady=5)
        self.prev_button = tk.Button(self.nav_frame, text="◀", command=self.move_left,
                                     font=self.button_font, bg="#555555", fg="white", relief=tk.FLAT)
        self.prev_button.pack(side=tk.LEFT, padx=5)
        self.next_button = tk.Button(self.nav_frame, text="▶", command=self.move_right,
                                     font=self.button_font, bg="#555555", fg="white", relief=tk.FLAT)
        self.next_button.pack(side=tk.RIGHT, padx=5)
        self.slider = tk.Scale(self.nav_frame, from_=0, to=0, orient=tk.HORIZONTAL,
                               command=self.slider_update, length=500,
                               bg="#2E2E2E", fg="white", highlightthickness=0, showvalue=False)
        self.slider.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.slider_value_label = tk.Label(self.nav_frame, text="", bg="#2E2E2E", fg="white")
        self.slider_value_label.pack(side=tk.LEFT, padx=5)

        # Фрейм для сводной таблицы
        self.summary_frame = tk.Frame(self.main_frame, bg="#2E2E2E", height=50)
        self.summary_frame.pack(side=tk.BOTTOM, anchor="w", fill=tk.BOTH,expand=True, padx=10, pady=10)
        self.summary_frame.pack_propagate(False)

        # Создаем фигуру и ось для графика
        self.figure, self.ax = plt.subplots(figsize=(8, 4), facecolor="#2E2E2E")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        # Панель инструментов
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame, pack_toolbar=False)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # Для tooltip - теперь окно не уничтожается, а скрывается (withdraw)
        self.tooltip_window = tk.Toplevel(self.root)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.withdraw()
        self.tooltip_label = tk.Label(self.tooltip_window, font=self.font, bg="#333333", fg="white", relief=tk.SOLID)
        self.tooltip_label.pack(padx=5, pady=5)

        # Выделение при hover
        self.face_colors = {}
        self.tooltip_window = None
        self.tooltip_label = None
        self.last_patch = None
        self.update_interval = 0  # 100 мс
        self.last_update_time = 0
        self.norm_tooltips = []
        self.norm_collection = None
        self.nack_tooltips = []
        self.nack_collection = None
        self.nack_points_collection = None
        self.nack_lines = []
        self.frame_collection = None
        self.frame_tooltips = []
        self.seq_info: dict = {}  # агрегированная информация по seq
        self.generated_color = 'lime'
        self.un_generated_color = 'orangered'
        self.last_event = None
        self.all_seq = None
        self.isLoadTable = False
        self.HOVER_UPDATE_INTERVAL = 0.1  # 100 мс
        self.highlighted_object = None
        self.hover_job = None

        self.data = None  # данные CSV
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)
        self.canvas.mpl_connect("figure_leave_event", self.on_leave)

        self.colors = {
            -1: "#FF0000",  # lost – красный
            1: "#00FF00",  # received – зеленый
            2: "#FFD700"  # resend – желтый
        }

        # Оптимизация отрисовки
        self.square_width = 0.8
        self.gap = 0.2

        # Параметры lazy rendering
        self.visible_count = 200
        self.current_start = 0

    # ============================================================================
    # Методы управления (слайдер, стрелки, обновление диапазона)
    # ============================================================================

    def slider_update(self, val):
        self.current_start = int(val)
        self.render_visible_range()
        # Обновляем метку, показывающую реальный seq первого norm-объекта
        if self.all_seq:
            self.slider_value_label.config(text=f"Seq: {self.all_seq[self.current_start]}")


    def move_left(self):
        new_start = max(0, self.current_start - self.visible_count)
        self.current_start = new_start
        self.slider.set(new_start)
        self.render_visible_range()


    def move_right(self):
        if self.data is None:
            return
        total = len(self.all_seq)
        new_start = min(total - self.visible_count, self.current_start + self.visible_count)
        self.current_start = new_start
        self.slider.set(new_start)
        self.render_visible_range()

    def get_all_seq(self):
        """Возвращает отсортированный список всех seq через `numpy` (в 5-10 раз быстрее)."""
        seq_column = self.data["seq_list"].values  # Получаем столбец как `numpy` массив
        flat_seq = np.concatenate(seq_column)  # Разворачиваем списки в один массив
        return sorted(set(flat_seq))  # Убираем дубликаты и сортируем


    def cache_seq_info(self, all_seq):
        """Кеширует seq_info при первой загрузке. Оптимизировано для скорости."""
        if self.seq_info:
            return  # Уже закешировано, ничего не делаем

        self.seq_info = {seq: {"final_state": 1, "events": []} for seq in all_seq}
        normal_df = self.data[self.data["type"] != 3]

        # Используем itertuples (быстрее, чем iterrows)
        for row in normal_df.itertuples(index=False, name=None):
            timestamp, seq_list, event_type, count = row[0], row[5], row[2], row[6]
            for seq in seq_list:
                if seq in self.seq_info:
                    self.seq_info[seq]["events"].append({
                        "timestamp": timestamp,
                        "type": event_type,
                        "count": count
                    })
                    self._update_final_state(seq, event_type)


    def _update_final_state(self, seq, event_type):
        """Обновляет final_state для события."""
        if event_type == 2:
            self.seq_info[seq]["final_state"] = 2
        elif event_type == -1 and self.seq_info[seq]["final_state"] != 2:
            self.seq_info[seq]["final_state"] = -1
        elif event_type == 1 and self.seq_info[seq]["final_state"] == 1:
            self.seq_info[seq]["final_state"] = 1


    def draw_normal_events(self, visible_seq, seq_to_index):
        """Отрисовывает нормальные события."""
        norm_rects, norm_colors = [], []
        self.norm_tooltips = []

        for seq in visible_seq:
            idx = seq_to_index.get(seq)
            if idx is None:
                continue

            x_coord = idx * (self.square_width + self.gap)
            norm_rects.append(plt.Rectangle((x_coord, 0.5), self.square_width, 0.5))
            norm_colors.append(self.colors.get(self.seq_info[seq]["final_state"], "#FFFFFF"))
            self.norm_tooltips.append(self.get_tooltip_text(seq))

        if self.norm_collection:
            self.norm_collection.remove()
        self.norm_collection = PatchCollection(norm_rects, facecolors=norm_colors, edgecolors='none', picker=True)
        self.ax.add_collection(self.norm_collection)


    def draw_nack_events(self, seq_to_index):
        """Отрисовывает NACK-события с корректным растяжением за границы."""
        nack_df = self.data[self.data["type"] == 3]
        nack_boxes = []
        nack_tooltips = []
        nack_points = []
        lines = []  # Для вычисления вертикального сдвига

        rect_height = 0.07
        line_spacing = 0.01
        first_line_offset = 0.075

        # Границы видимой области
        min_visible_seq = min(seq_to_index.keys(), default=None)
        max_visible_seq = max(seq_to_index.keys(), default=None)
        if min_visible_seq is None or max_visible_seq is None:
            return  # Нет данных для отрисовки

        for _, row in nack_df.iterrows():
            seq_list = row["seq_list"]
            formatted_time = row["timestamp"].strftime('%Y-%m-%d %H:%M:%S')
            milliseconds = int(row["timestamp"].microsecond / 1000)
            formatted_time += f":{milliseconds:03d}"

            # Определяем реальные границы NACK
            min_seq = min(seq_list)
            max_seq = max(seq_list)

            # Определяем начало и конец отрисовки
            start_seq = max(min_seq, min_visible_seq)  # Если NACK выходит влево – тянем с начала области
            end_seq = max_seq  # Если NACK уходит вправо – пусть продолжается

            # Если конец за границами видимой области, то продолжаем тянуть до конца текущей области
            if end_seq > max_visible_seq:
                end_seq = max_visible_seq

            min_idx = seq_to_index.get(start_seq)
            max_idx = seq_to_index.get(end_seq)
            if min_idx is None or max_idx is None:
                continue

            start_interval = min_idx
            end_interval = max_idx
            line_index = None

            # Проверяем пересечение с уже занятыми линиями
            for i, intervals in enumerate(lines):
                if all(not intervals_overlap(start_interval, end_interval, a, b) for (a, b) in intervals):
                    line_index = i
                    intervals.append((start_interval, end_interval))
                    break

            if line_index is None:
                line_index = len(lines)
                lines.append([(start_interval, end_interval)])

            # Корректируем x-координаты, растягивая NACK на всю видимую область
            x_start = min_idx * (self.square_width + self.gap)
            x_end = max_idx * (self.square_width + self.gap) + self.square_width
            width_rect = x_end - x_start

            # Расположение прямоугольника по вертикали
            rect_y = 0.5 - first_line_offset - line_index * (rect_height + line_spacing)

            # Создание прямоугольника для NACK
            box = plt.Rectangle((x_start, rect_y), width_rect, rect_height, color="cyan", alpha=0.7)
            box.tooltip = f"NACK: {seq_list}\n Timestamp: {formatted_time}"
            nack_boxes.append(box)
            nack_tooltips.append(box.tooltip)

            # Точки (расположены строго под seq)
            for s in seq_list:
                idx = seq_to_index.get(s)
                if idx is None:
                    continue
                x_center = idx * (self.square_width + self.gap) + self.square_width / 2
                y_center = rect_y + rect_height / 2
                nack_points.append((x_center, y_center))

        # Обновляем уровни NACK, чтобы update_axes получил актуальное значение
        self.nack_lines = lines
        # Обновляем коллекцию NACK (боксы и точки)
        self._update_nack_collection(nack_boxes, nack_tooltips, nack_points)


    def _update_nack_collection(self, nack_boxes, nack_tooltips, nack_points):
        """Обновляет коллекцию NACK-событий, корректно перерисовывая точки."""

        # Удаляем старые NACK-боксы
        if self.nack_collection:
            self.nack_collection.remove()
            self.nack_collection = None

        if nack_boxes:
            self.nack_collection = PatchCollection(nack_boxes, facecolors="cyan", alpha=0.7, edgecolor="none",
                                                   picker=True)
            self.ax.add_collection(self.nack_collection)
            self.nack_tooltips = nack_tooltips
        else:
            self.nack_collection = None

        # Удаляем старые NACK-точки
        if self.nack_points_collection:
            self.nack_points_collection.remove()
            self.nack_points_collection = None

        # Добавляем новые точки
        if nack_points:
            x, y = zip(*nack_points) if nack_points else ([], [])
            self.nack_points_collection = self.ax.scatter(x, y, s=25, marker="o", color="red", zorder=3)
        else:
            self.nack_points_collection = None


    def draw_frame_boxes(self, visible_seq):
        """Отрисовывает Frame-боксы."""
        frame_boxes, frame_colors, frame_tooltips = [], [], []
        block_size = 10
        for i in range(0, len(visible_seq), block_size):
            block = visible_seq[i:i + block_size]
            block_state = "Generated"
            block_color = self.generated_color

            for s in block:
                if self.seq_info.get(s, {}).get("final_state") == -1:
                    block_state = "UnGenerated"
                    block_color = self.un_generated_color
                    break

            x_start = i * (self.square_width + self.gap)
            block_width = len(block) * (self.square_width + self.gap)

            rect = plt.Rectangle((x_start, 1.1), block_width, 0.2)
            frame_boxes.append(rect)
            frame_colors.append(block_color)
            frame_tooltips.append(f"Frame: {block_state} ({block[0]} - {block[-1]})")

            self.ax.text(x_start + block_width / 2, 1.2, f"Frame: {block_state}", color="white",
                         fontsize=10, ha="center", va="center", zorder=2)

        self._update_frame_collection(frame_boxes, frame_colors, frame_tooltips)


    def _update_frame_collection(self, frame_boxes, frame_colors, frame_tooltips):
        """Обновляет коллекцию Frame-боксов."""
        if self.frame_collection:
            self.frame_collection.remove()
        if frame_boxes:
            self.frame_collection = PatchCollection(frame_boxes, facecolors=frame_colors, alpha=0.5, edgecolor="none",
                                                    picker=True)
            self.ax.add_collection(self.frame_collection)
            self.frame_tooltips = frame_tooltips
        else:
            self.frame_collection = None


    def update_axes(self, visible_seq, lines):
        """Обновляет оси графика с динамическим нижним пределом для nack-событий."""
        total_visible = len(visible_seq)
        total_width = total_visible * (self.square_width + self.gap)

        # Если nack-события есть, вычисляем нижнюю границу оси Y
        if len(lines) > 0:
            max_nack_level = len(lines)
            lowest_line_index = max_nack_level - 1
            rect_height = 0.07
            line_spacing = 0.01
            first_line_offset = 0.075
            # Координата y для самой верхней точки нижней nack-линии (rect_y)
            lowest_y = 0.5 - first_line_offset - lowest_line_index * (rect_height + line_spacing)
            margin = 0.05  # Дополнительный запас
            min_y = lowest_y - margin
        else:
            # Если нет nack, нижняя граница чуть ниже нормальных объектов
            min_y = 0.5 - 0.05

        self.ax.set_xlim(0, total_width)
        self.ax.set_ylim(min_y, 1.5)
        self.ax.get_yaxis().set_visible(False)

        x_ticks = [i * (self.square_width + self.gap) + self.square_width / 2 for i in range(total_visible)]
        x_labels = [str(seq) for seq in visible_seq]

        self.ax.set_xticks(x_ticks)
        self.ax.set_xticklabels(x_labels, color="white", fontsize=10, rotation=90)


    def render_visible_range(self):
        if self.data is None:
            return

        self.all_seq = self.get_all_seq()
        if not self.all_seq:
            return
        self.setup_slider()
        visible_seq = self.all_seq[self.current_start:self.current_start + self.visible_count]
        seq_to_index = {seq: i for i, seq in enumerate(visible_seq)}

        # 1. Кеширование seq_info
        self.cache_seq_info(self.all_seq)

        # 2. Отрисовка нормальных событий
        self.draw_normal_events(visible_seq, seq_to_index)

        # 3. Отрисовка NACK-событий
        self.draw_nack_events(seq_to_index)

        # 4. Отрисовка Frame-боксов
        self.draw_frame_boxes(visible_seq)

        # 5. Обновление осей
        self.update_axes(visible_seq, self.nack_lines)

        # 6. Обновление сводной таблицы
        if not self.isLoadTable:
            self.update_summary_table()
            self.isLoadTable = True

        # 7. Обновление графика
        self.canvas.draw_idle()


    def setup_slider(self):
        """Создаёт слайдер, который работает по индексам, а не по значениям seq."""
        if not self.all_seq:
            return  # Если данных нет, ничего не делаем

        slider_from = 0
        slider_to = max(0, len(self.all_seq) - self.visible_count)
        self.slider.config(from_=slider_from, to=slider_to, resolution=1)
        self.slider.set(self.current_start)
        self.slider_value_label.config(text=f"Seq: {self.all_seq[self.current_start]}")
        if not self.slider.winfo_ismapped():
            self.slider.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)


    def update_visible_range(self, new_start):
        """Обновляет отображаемый диапазон, устанавливая новый current_start и перерисовывая видимую область."""
        self.current_start = new_start
        self.render_visible_range()


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
        """
        Если окно tooltip открыто, обновляет его текст с учётом последних настроек.
        Использует последнее сохранённое событие (self.last_event) и функцию _find_tooltip.
        """
        if not self.tooltip_window or not hasattr(self, "last_event"):
            return

        _, tooltip_text, _ = self._find_tooltip(self.last_event, apply_check_vars=True)

        if tooltip_text:
            for widget in self.tooltip_window.winfo_children():
                widget.config(text=tooltip_text)
        else:
            self.remove_tooltip()



    def clear_graph(self):
        """Очищает график и все связанные коллекции перед построением нового графика."""
        self.ax.clear()
        # Сброс всех коллекций, если они используются
        self.norm_collection = None
        self.nack_collection = None
        self.frame_collection = None
        # Можно сбросить и другие переменные, связанные с предыдущей отрисовкой
        self.norm_tooltips = []
        self.nack_tooltips = []
        self.frame_tooltips = []
        self.seq_info = {}
        # Обновляем canvas, чтобы изменения отобразились
        self.canvas.draw()


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
            seq_lists = []
            for row in df.itertuples(index=False, name="Row"):
                seq_val = getattr(row, 'seq')
                type_val = getattr(row, 'type')
                seq_lists.append(self.parse_seq_fast(seq_val, type_val))
            df["seq_list"] = seq_lists
            if not {"timestamp", "seq", "type"}.issubset(df.columns):
                raise ValueError("CSV не содержит столбцы: timestamp, seq, type")
            df["type"] = df["type"].astype(float)
            if "count" not in df.columns:
                df["count"] = 1
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", errors="coerce", utc=True).dt.tz_convert(get_system_timezone())
            df = df.dropna(subset=["timestamp"])
            self.data = df
            # Проверяем, что файл file_path - строка
            if isinstance(file_path, str):
                filename = os.path.basename(file_path)
                self.file_label.config(text=f"Выбран файл: {filename}")
            else:
                self.file_label.config(text="Ошибка: Некорректный путь к файлу")
            # Отображаем основной контейнер, если он ещё не показан
            if not self.main_frame.winfo_ismapped():
                self.main_frame.pack(fill=tk.BOTH, expand=True)
            # Очищаем график перед построением нового
            self.clear_graph()
            self.render_visible_range()
        except Exception as e:
            self.file_label.config(text=f"Ошибка: {e}")

    @staticmethod
    def parse_seq_fast(seq, event_type):
        """
        Быстрый парсер для столбца seq.
        Для event_type == 3 – возвращает список чисел, иначе – только первый элемент.
        """
        if pd.isna(seq):
            return []
        # Если seq – строка, убираем лишние пробелы
        if isinstance(seq, str):
            seq = seq.strip()
            # Если строка выглядит как список: "[...]"
            if seq.startswith("[") and seq.endswith("]"):
                try:
                    parsed = ast.literal_eval(seq)
                except Exception as e:
                    print(f"[DEBUG] Ошибка парсинга: {seq}: {e}")
                    return []
                return [int(x) for x in parsed] if event_type == 3 else ([int(parsed[0])] if parsed else [])
            # Если строка содержит запятую, разделяем по ней
            elif "," in seq:
                try:
                    parts = [part.strip() for part in seq.split(",")]
                    numbers = [int(part) for part in parts if part]
                except Exception as e:
                    print(f"[DEBUG] Ошибка разделения: {seq}: {e}")
                    return []
                return numbers if event_type == 3 else numbers[:1]
            else:
                try:
                    return [int(seq)]
                except Exception as e:
                    print(f"[DEBUG] Ошибка преобразования: {seq}: {e}")
                    return []
        # Если уже число или список – пытаемся привести к числам
        elif isinstance(seq, list):
            if event_type == 3:
                try:
                    return [int(x) for x in seq]
                except Exception as e:
                    print(f"[DEBUG] Ошибка при обработке списка: {seq}: {e}")
                    return []
            else:
                try:
                    return [int(seq[0])] if seq else []
                except Exception as e:
                    print(f"[DEBUG] Ошибка при обработке списка: {seq}: {e}")
                    return []
        else:
            try:
                return [int(seq)]
            except Exception as e:
                print(f"[DEBUG] Ошибка преобразования: {seq}: {e}")
                return []


    def update_summary_table(self):
        """
        Вычисляет и обновляет сводную таблицу подсчёта для всех seq,
        присутствующих в загруженных данных.
        """
        all_seq = self.all_seq
        total_seq = len(all_seq)
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
            self.summary_label.pack(side=tk.BOTTOM, anchor="w", padx=5, pady=5)
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
                # Форматируем дату и время с миллисекундами
                formatted_time = event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                milliseconds = int(event['timestamp'].microsecond / 1000)
                formatted_time += f":{milliseconds:03d}"

                if event["type"] in (1, -1):
                    timestamps.append("Timestamp: " + formatted_time)
                else:
                    timestamps.append(formatted_time)
            tooltip_parts.append("\n".join(timestamps))

        if self.check_vars["events"].get():
            mapping = {-1: "Lost", 1: "Received", 2: "Resend"}
            event_types = [mapping.get(event["type"], str(event["type"])) for event in events if
                           not pd.isna(event["type"])]
            tooltip_parts.append("Events: " + ", ".join(event_types))

        if self.check_vars["count"].get():
            counts = [str(event["count"]) for event in events]
            tooltip_parts.append("Count: " + ", ".join(counts))

        return "\n".join(tooltip_parts)

    @profile_time
    def on_hover(self, event: Any):
        """Обновлённый обработчик hover-а с `after()`, уменьшающий нагрузку на CPU."""

        # Если есть старый `after()`, отменяем его
        if hasattr(self, "hover_job") and self.hover_job:
            self.root.after_cancel(self.hover_job)

        # Запускаем `after()`, который выполнит `self._handle_hover()` через 200 мс
        self.hover_job = self.root.after(200, lambda: self._handle_hover(event))

    @profile_time
    def _handle_hover(self, event: Any):
        """Основная логика hover-а, которая вызывается `after()` (раз в 200 мс)."""
        self.hover_job = None  # Очищаем `after()` (он выполнен)

        # Проверяем, изменилась ли позиция курсора (избавляемся от лишних вызовов)
        if hasattr(self, "last_event") and self.last_event is not None:
            if self.last_event.x == event.x and self.last_event.y == event.y:
                return  # Если курсор не двигался, ничего не делаем

        self.last_event = event  # Запоминаем последнее событие

        # Проверяем, внутри ли курсор области графика
        if not self.ax.get_window_extent().contains(event.x, event.y):
            self.remove_tooltip()
            return

        # Проверяем, есть ли данные для hover
        if not any([self.norm_collection, self.nack_collection, self.frame_collection]):
            self.remove_tooltip()
            return

        # Находим объект под курсором
        highlight_index, tooltip_text, current_coll = self._find_tooltip(event)

        if current_coll is None:  # ДОБАВЬТЕ ЭТУ ПРОВЕРКУ!
            self.remove_tooltip()
            return

        # Проверяем, уже ли выделен этот же объект
        if hasattr(self, "highlighted_object") and self.highlighted_object == (highlight_index, current_coll):
            return  # Уже выделен — ничего не делаем


        self.highlighted_object = (highlight_index, current_coll)

        # Если нашли объект — выделяем его и показываем tooltip
        try:
            new_edge_colors = current_coll.get_edgecolors()
            new_line_widths = current_coll.get_linewidths()
            if current_coll not in self.face_colors:
                orig_fc = current_coll.get_edgecolors()
                orig_lw = current_coll.get_linewidths()

                orig_fc = orig_fc.copy() if orig_fc is not None else None
                orig_lw = orig_lw.copy() if orig_lw is not None else None

                self.face_colors[current_coll] = (orig_fc, orig_lw)

            if new_edge_colors is not None and new_edge_colors.size > highlight_index:
                new_edge_colors = new_edge_colors.copy()
                new_edge_colors[highlight_index] = (1, 1, 1, 1)  # Белый контур

            if new_line_widths is not None and new_line_widths.size > highlight_index:
                new_line_widths = new_line_widths.copy()
                new_line_widths[highlight_index] = 3

            if new_edge_colors is not None:
                current_coll.set_edgecolors(new_edge_colors)
            if new_line_widths is not None:
                current_coll.set_linewidths(new_line_widths)


        except (AttributeError, ValueError, IndexError) as e:
            print(f"[ERROR] Ошибка при выделении объекта: {e}")

            self.show_tooltip(tooltip_text)

            # Восстановить исходные цвета лица (только если был установлен цвет лица для объекта)
            for coll, (orig_fc, orig_lw) in self.face_colors.items():
                try:
                    if orig_fc is not None:
                        coll.set_edgecolors(orig_fc)
                    if orig_lw is not None:
                        coll.set_linewidths(orig_lw)
                except Exception as e:
                    print(f"[INFO] Exception: {e}")

            self.face_colors.clear()
            self.highlighted_object = None
            self.canvas.draw_idle()


    def _find_tooltip(self, event, apply_check_vars=True):
        """
        Оптимизированный поиск tooltip-а: сначала проверяет, внутри ли графика курсор,
        затем сразу возвращает первый найденный объект без лишних проверок.

        :param event: Событие курсора
        :param apply_check_vars: Нужно ли применять фильтрацию полей согласно чекбоксам
        :return: (index, tooltip_text, collection)
        """
        # Быстрая проверка: находимся ли мы вообще внутри области графика?
        if not self.ax.get_window_extent().contains(event.x, event.y):
            return None, None, None

        if self.norm_collection is None and self.nack_collection is None and self.frame_collection is None:
            return None, None, None

        # Коллекции для проверки
        collections = [
            (self.norm_collection, self.norm_tooltips),
            (self.nack_collection, self.nack_tooltips),
            (self.frame_collection, self.frame_tooltips)
        ]

        # Перебираем коллекции вручную, чтобы избежать ошибки с присвоением
        for collection, tooltips in collections:
            if collection is None:
                continue

            contains_info = collection.contains(event)  # Вызываем 1 раз
            if not contains_info[0]:  # Если курсор не попал в объект — пропускаем
                continue

            info = contains_info[1]  # Вытаскиваем вторую часть ответа
            if info is None or "ind" not in info or len(info["ind"]) == 0:
                continue

            idx = info["ind"][0]
            tooltip_text = self._filter_tooltip(tooltips[idx]) if apply_check_vars else tooltips[idx]

            return idx, tooltip_text, collection  # Нашли объект — возвращаем

        return None, None, None  # Если ничего не нашли


    def _filter_tooltip(self, tooltip_text):
        """
        Фильтрует содержимое tooltip согласно активным чекбоксам.

        :param tooltip_text: Оригинальный текст tooltip.
        :return: Отфильтрованный текст.
        """
        lines = tooltip_text.split("\n")
        filtered_lines = []

        for line in lines:
            if "Seq:" in line and not self.check_vars["seq"].get():
                continue
            if "Timestamp:" in line and not self.check_vars["timestamp"].get():
                continue
            if "Events:" in line and not self.check_vars["events"].get():
                continue
            if "Count:" in line and not self.check_vars["count"].get():
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines) if filtered_lines else None


    def show_tooltip(self, text):
        """
        Отображает tooltip рядом с курсором.
        Если окно tooltip уже существует, то оно лишь показывается (deiconify) и обновляется его положение и текст.
        """
        x_root, y_root = self.root.winfo_pointerxy()
        if not self.tooltip_window:  # Создаем окно только один раз
            self.tooltip_window = tk.Toplevel(self.root)
            self.tooltip_window.wm_overrideredirect(True)  # Убираем рамку
            self.tooltip_label = tk.Label(self.tooltip_window, text="", font=self.font,
                                          bg="#333333", fg="white", relief=tk.SOLID)  # Создаем label один раз
            self.tooltip_label.pack(padx=5, pady=5)

        self.tooltip_label.config(text=text)  # Обновляем текст
        self.tooltip_window.wm_geometry(f"+{x_root + 10}+{y_root + 10}")  # обновляем позицию
        self.tooltip_window.deiconify()  # Показываем окно

    def remove_tooltip(self):
        """
        Скрываем окно tooltip (withdraw),
        чтобы потом можно было быстро обновлять его содержимое.
        """
        if self.tooltip_window:
            self.tooltip_window.withdraw()

    @profile_time
    def on_leave(self, _=None):
        """
        Скрывает tooltip, если мышь вышла за пределы графика.
        """
        self.remove_tooltip()
        self.highlighted_object = None  # Сбрасываем выделенный объект
        self.canvas.draw_idle()


if __name__ == "__main__":
    root = tk.Tk()
    app = CSVGraphApp(root)
    root.mainloop()
