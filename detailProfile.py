import cProfile
import pstats
import functools
import io

def profile_detailed(func):
    """Декоратор для детального профилирования метода с фильтрацией"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()

        # Фильтруем только функции, относящиеся к твоему коду
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.strip_dirs().sort_stats("cumulative").print_stats(10)  # ТОП-10 вызовов

        print(stream.getvalue())  # Выводим отфильтрованные данные
        return result

    return wrapper
