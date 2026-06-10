import threading


def sleep_with_stop(stop_event: threading.Event, seconds: float):
    stop_event.wait(seconds)
