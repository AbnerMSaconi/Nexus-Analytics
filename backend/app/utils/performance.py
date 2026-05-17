import time
import asyncio
from functools import wraps
from app.utils.logger import logger
from contextlib import contextmanager, asynccontextmanager

class PerformanceMonitor:
    """
    Utilitário para monitorar o desempenho de funções síncronas e assíncronas.
    """
    
    @staticmethod
    @contextmanager
    def timer(label: str):
        start_time = time.perf_counter()
        try:
            yield
        finally:
            end_time = time.perf_counter()
            duration = end_time - start_time
            logger.info(f"⏱️  [PERF] {label}: {duration:.4f} segundos")

    @staticmethod
    @asynccontextmanager
    async def async_timer(label: str):
        start_time = time.perf_counter()
        try:
            yield
        finally:
            end_time = time.perf_counter()
            duration = end_time - start_time
            logger.info(f"⏱️  [ASYNC PERF] {label}: {duration:.4f} segundos")

def monitor_perf(label: str):
    """Decorator para monitorar o desempenho de funções."""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                result = await func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                logger.info(f"⏱️  [PERF] {label or func.__name__}: {duration:.4f}s")
                return result
            return wrapper
        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                logger.info(f"⏱️  [PERF] {label or func.__name__}: {duration:.4f}s")
                return result
            return wrapper
    return decorator
