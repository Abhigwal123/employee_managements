import logging
import sys


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    
    # Configure trace logger for detailed request/response logging
    trace_logger = logging.getLogger('trace')
    trace_logger.setLevel(logging.DEBUG)
    if not trace_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('[TRACE] Backend: %(message)s')
        console_handler.setFormatter(formatter)
        trace_logger.addHandler(console_handler)
        trace_logger.propagate = False



