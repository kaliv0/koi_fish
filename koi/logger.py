from koi.constants import LogLevel


class Logger:
    @classmethod
    def log(cls, msg, end="\n", flush=False):
        print(msg, end=end, flush=flush)  # white

    @classmethod
    def error(cls, msg, end="\n", flush=False):
        cls._log(LogLevel.ERROR, msg, end=end, flush=flush)  # red

    @classmethod
    def success(cls, msg, end="\n", flush=False):
        cls._log(LogLevel.SUCCESS, msg, end=end, flush=flush)  # green

    @classmethod
    def start(cls, msg, end="\n", flush=False):
        cls._log(LogLevel.START, msg, end=end, flush=flush)  # yellow

    @classmethod
    def fail(cls, msg, end="\n", flush=False):
        cls._log(LogLevel.FAIL, msg, end=end, flush=flush)  # blue

    @classmethod
    def debug(cls, msg, end="\n", flush=False):
        cls._log(LogLevel.DEBUG, msg, end=end, flush=flush)  # purple

    @classmethod
    def info(cls, msg, end="\n", flush=False):
        cls._log(LogLevel.INFO, msg, end=end, flush=flush)  # light blue

    @classmethod
    def _log(cls, level, msg, end="\n", flush=False):
        print(f"\033[{level}m{msg}\033[00m", end=end, flush=flush)
