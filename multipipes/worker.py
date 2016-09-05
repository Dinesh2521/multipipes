import os
import signal
from multiprocessing import Process

from .exceptions import MaxRequestsException


class Worker:
    def __init__(self, task=None, *,
                 manager=None, daemon=None):
        self.task = task
        self.manager = manager
        self.daemon = daemon
        self.exit_signal = True

    def run(self):
        signal.signal(signal.SIGINT, self._stop)

        try:
            self.task.run_forever()
        except MaxRequestsException:
            self.send_event({'type': 'max_requests'})

    def _stop(self, signum, frame):
        self.task.exit_signal = True

    def send_event(self, event):
        if self.manager:
            event['pid'] = os.getpid()
            self.manager.send_event(event)

    def start(self):
        self.process = Process(target=self.run)
        self.process.start()
        self.pid = self.process.pid

        if self.manager:
            self.manager.register_worker(self.pid, self)

        self.exit_signal = False

    def stop(self):
        """Warning: if `stop` is called just after `start`, the SIGINT
        might be ignored by the child process because it hasn't
        registered the callback yet.
        """
        if self.exit_signal:
            return
        os.kill(self.pid, signal.SIGINT)

    def restart(self, timeout=None):
        self.stop()
        try:
            self.join(timeout=timeout)
        except TimeoutError:
            self.terminate()
            self.join()
        self.start()

    def join(self, timeout=None):
        self.process.join(timeout)

    def terminate(self):
        self.process.terminate()

    def is_alive(self):
        self.process.is_alive()
