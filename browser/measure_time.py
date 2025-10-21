import threading
import time
import json


class MeasureTime:
    def __init__(self):
        self.lock = threading.Lock()
        self.file = open("browser_trace.json", "w")
        self.file.write('{"traceEvents": [')
        self.file.write(create_time_entry("process_name", "M",
                        {"cat": "__metadata", "args": {"name": "Browser"}}))
        self.file.flush()

    def time(self, name):
        with self.lock:
            tid = threading.get_ident()
            new_entry = create_time_entry(name, "B", {"tid": tid})
            self.file.write(f", {new_entry}")
            self.file.flush()

    def stop(self, name):
        with self.lock:
            tid = threading.get_ident()
            new_entry = create_time_entry(name, "E", {"tid": tid})
            self.file.write(f", {new_entry}")
            self.file.flush()
    
    def finish(self):
        with self.lock:
            for thread in threading.enumerate():
                new_entry = create_time_entry("thread_name", "M",
                    {"tid": thread.ident, "args": {"name": thread.name}})
                self.file.write(f", {new_entry}")
            self.file.write("]}")
            self.file.close()


def create_time_entry(name: str, phase: str, metadata: dict) -> str:
    """
    Creates a JSON time entry using trace event format.

    name: process name
    phase: event phase
    metadata: extra metadata for the event
    """
    ts = time.time() * 1000000
    new_entry = {
        "name": name,
        "ph": phase,
        "ts": str(ts),
        "pid": 1,
        "cat": "_",
        **metadata,
    }
    return json.dumps(new_entry)
