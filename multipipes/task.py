"""Wrapper around a target function."""

import types
import inspect
from multiprocessing import queues

from .utils import deadline
from .exceptions import MaxRequestsException, TimeoutNotSupportedError


def _inspect_func(target):
    params = inspect.signature(target).parameters
    accept_timeout = all(param.default is not inspect.Signature.empty
                         for param in params.values())
    params_count = len(params)
    return params_count, accept_timeout


class Task:
    def __init__(self, target, indata=None, outdata=None, *,
                 max_execution_time=None, max_requests=None,
                 timeout=None, polling_timeout=0.5):
        self.target = target
        self.params_count, self.accept_timeout = _inspect_func(target)
        self.requests_count = 0

        self.indata = indata
        self.outdata = outdata
        self.exit_signal = False
        self.running = True

        self.timeout = timeout
        self.polling_timeout = polling_timeout

        if self.timeout and not self.accept_timeout:
            raise TimeoutNotSupportedError()

        self.max_execution_time = max_execution_time
        self.max_requests = max_requests

    def step(self):
        args = self.pull()
        result = self(*args)
        self.push(result)

        if self.requests_count == self.max_requests:
            raise MaxRequestsException()

    def run_forever(self):
        while self.running:
            try:
                self.step()
            except KeyboardInterrupt:
                self.exit_signal = True

    def __call__(self, *args):
        if len(args) != self.params_count:
            if not self.timeout:
                return

        with deadline(self.max_execution_time):
            result = self.target(*args)

        self.requests_count += 1
        return result

    def _read_from_indata(self):
        if self.timeout:
            if self.timeout <= self.polling_timeout:
                try:
                    return self.indata.get(timeout=self.timeout)
                except queues.Empty:
                    return
            else:
                # polling_timeout as much time then delta
                times = int(self.timeout // self.polling_timeout)
                delta = self.timeout - self.polling_timeout
                for _ in range(times):
                    try:
                        return self.indata.get(timeout=self.polling_timeout)
                    except queues.Empty:
                        if self.exit_signal:
                            self.running = False
                            return
                try:
                    return self.indata.get(timeout=delta)
                except queues.Empty:
                    return
        else:
            # while true: polling_timeout
            while True:
                try:
                    return self.indata.get(timeout=self.polling_timeout)
                except queues.Empty:
                    if self.exit_signal:
                        self.running = False
                        return

    def pull(self):
        if self.indata:
            args = self._read_from_indata()

        if args is None:
            args = ()

        if not isinstance(args, tuple):
            args = (args, )

        return args

    def push(self, result):
        if result is not None and self.outdata:
            if isinstance(result, types.GeneratorType):
                for item in result:
                    self.outdata.put(item)
            else:
                self.outdata.put(result)
