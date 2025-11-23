import time

class Metrics:
    def __init__(self):
        self.history = []

    def record_query(self, domain, mode, duration, status):
        self.history.append({
            'timestamp': time.time(),
            'domain': domain,
            'mode': mode,
            'duration': duration,
            'status': status
        })

    def get_average_latency(self):
        if not self.history:
            return 0
        total_duration = sum(entry['duration'] for entry in self.history)
        return total_duration / len(self.history)

    def get_query_count(self):
        return len(self.history)
