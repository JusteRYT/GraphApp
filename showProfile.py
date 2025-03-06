import functools
import time
from collections import defaultdict

# Храним вызовы методов
call_stats = defaultdict(lambda: {"count": 0, "total_time": 0.0, "last_log": 0})

def profile_time(func):
    """Декоратор для замера времени выполнения метода с группировкой повторных вызовов."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global call_stats

        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()

        exec_time = end_time - start_time
        func_name = func.__name__

        # Обновляем статистику вызовов
        call_stats[func_name]["count"] += 1
        call_stats[func_name]["total_time"] += exec_time

        # Логируем раз в секунду
        current_time = time.time()
        if current_time - call_stats[func_name]["last_log"] >= 1:
            avg_time = call_stats[func_name]["total_time"] / call_stats[func_name]["count"]
            print(f"[PROFILE] {func_name} вызван {call_stats[func_name]['count']} раз. "
                  f"Среднее время: {avg_time:.6f} сек. "
                  f"Общее время: {call_stats[func_name]['total_time']:.6f} сек.")
            call_stats[func_name]["count"] = 0
            call_stats[func_name]["total_time"] = 0.0
            call_stats[func_name]["last_log"] = current_time

        return result
    return wrapper
