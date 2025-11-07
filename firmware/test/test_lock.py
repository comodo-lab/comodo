# test_massflow_lock.py
import time
import threading

import os
import fcntl
from contextlib import contextmanager

ERROR_TIMEOUT = 10
REPETITION_TIME = 2

LOCK_FILE = os.environ.get("MASSFLOW_LOCK_FILE", f"{os.getcwd()}/massflow.lock")


@contextmanager
def serial_lock():
    """
    Cross-process lock using flock on a shared file.

    All propar calls to the same device must be wrapped in this.
    """
    fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

def fake_read(name, i):
    with serial_lock():
        print(f"{name} start {i}")
        time.sleep(0.2)
        print(f"{name} end   {i}")

def worker(name):
    for i in range(5):
        fake_read(name, i)

threads = [
    threading.Thread(target=worker, args=("massflow",)),
    threading.Thread(target=worker, args=("massflow_temp",)),
    threading.Thread(target=worker, args=("massflow_pressure_upstream",)),
]

for t in threads:
    t.start()
for t in threads:
    t.join()
