import time
import functools

def profile_time(func):
    """Декоратор для замера времени выполнения метода"""
    @functools.wraps(func)  # Сохраняет имя и документацию оригинальной функции
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        print(f"Метод {func.__name__} выполнен за {end_time - start_time:.6f} секунд")
        return result
    return wrapper
