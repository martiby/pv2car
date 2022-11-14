import time

class Timer:
    """
    Simple Timer

    start(duration=None, keep_running=False)
    stop(duration=None)

    is_stopped()
    is_running(duration=None)
    is_expired(duration=None)

    get_elapsed()
    get_remaining()
    """

    def __init__(self, duration=None):
        """
        :param duration: seconds
        """
        self.duration = duration  # timer duration in seconds
        self._start_time = None  # start timestamp: time.perf_counter()

    def start(self, duration=None, restart=True):
        if self._start_time and not restart:
            pass
        else:
            self.update_duration(duration)
            if self.duration is not None:
                self._start_time = time.perf_counter()

    def stop(self, duration=None):
        self.update_duration(duration)
        self._start_time = None

    def is_stopped(self):
        return True if self._start_time is None else False

    def is_running(self):
        t = time.perf_counter()
        if self._start_time and t < self._start_time + self.duration:  # check elapsed time
            return True
        else:
            return False

    def is_expired(self):
        t = time.perf_counter()
        if self._start_time and t >= self._start_time + self.duration:  # check elapsed time
            return True
        else:
            return False

    def update_duration(self, duration):
        if duration is not None:  # set new duration
            self.duration = duration

        if self.duration is None:  # if duration is not specified, timer is disabled
            self._start_time = None

    def get_elapsed(self):
        try:
            return min(time.perf_counter() - self._start_time, self.duration)  # calculate elapsed time and limit
        except:
            return 0

    def get_remaining(self):
        try:
            return max(self._start_time + self.duration - time.perf_counter(), 0)  # calculate remaining time
        except:
            return 0 if self.duration is None else self.duration

    def get_info(self):
        if self.is_stopped():
            return "stop"
        elif self.is_running():
            return "run ({}/{})".format(round(self.get_elapsed()), self.duration)
        elif self.is_expired():
            return "expired ({})".format(self.duration)
        else:
            return "error"

    def set_expired(self):

        self._start_time = time.perf_counter() - self.duration


class IntervalTimer:
    """
    Simple interval timer. Aligned to system time
    """

    def __init__(self, interval):
        """
        Init
        :param interval: seconds
        """
        self.interval = interval
        self.t = None

    def __call__(self):
        """
        Run timer.
        :return: True if interval is jumped over else False
        """
        t = int(time.time() / self.interval)
        if self.t is None:
            self.t = t
        r = t != self.t
        self.t = t
        return r

    def get_elapsed(self):
        """
        Get time elapsed since last interval
        :return: seconds
        """
        try:
            return time.time() - self.t * self.interval
        except:
            return 0

    def get_remaining(self):
        """
        Get time remaining to next interval
        :return: seconds
        """
        try:
            return (self.t + 1) * self.interval - time.time()
        except:
            return 0


if __name__ == "__main__":

    # === Demo: Timer ====

    # tmr = Timer(4)
    # print("{} {} {:.1f} {:.1f}".format(tmr.is_running(), tmr.is_expired(), tmr.get_elapsed(), tmr.get_remaining()))
    # tmr.start()
    # while True:
    #     print("{} {} {:.1f} {:.1f}".format(tmr.is_running(), tmr.is_expired(), tmr.get_elapsed(), tmr.get_remaining()))
    #     time.sleep(0.5)

    # === Demo: Interval ====

    tmr = IntervalTimer(20)
    while True:
        print(tmr(), tmr.get_elapsed(), tmr.get_remaining())
        time.sleep(0.5)
