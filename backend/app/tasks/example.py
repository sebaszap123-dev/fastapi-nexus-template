import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.example.ping")
def ping() -> str:
    """
    Simple example task that returns 'pong'.

    Usage:
        from app.tasks.example import ping
        result = ping.delay()
        print(result.get())  # 'pong'
    """
    logger.info("Ping task executed")
    return "pong"


@celery_app.task(name="app.tasks.example.add_numbers")
def add_numbers(a: int, b: int) -> int:
    """
    Example task that adds two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    result = a + b
    logger.info(f"Added {a} + {b} = {result}")
    return result
