class Level:
    ERROR = 91
    SUCCESS = 92
    START = 93
    FAIL = 94
    DEBUG = 95
    INFO = 96


class Logger:
    @classmethod
    def log(cls, msg, end="\n", flush=False):
        print(msg, end=end, flush=flush)  # white

    @classmethod
    def error(cls, msg, end="\n", flush=False):
        cls._log(Level.ERROR, msg, end=end, flush=flush)  # red

    @classmethod
    def success(cls, msg, end="\n", flush=False):
        cls._log(Level.SUCCESS, msg, end=end, flush=flush)  # green

    @classmethod
    def start(cls, msg, end="\n", flush=False):
        cls._log(Level.START, msg, end=end, flush=flush)  # yellow

    @classmethod
    def fail(cls, msg, end="\n", flush=False):
        cls._log(Level.FAIL, msg, end=end, flush=flush)  # blue

    @classmethod
    def debug(cls, msg, end="\n", flush=False):
        cls._log(Level.DEBUG, msg, end=end, flush=flush)  # purple

    @classmethod
    def info(cls, msg, end="\n", flush=False):
        cls._log(Level.INFO, msg, end=end, flush=flush)  # light blue

    @classmethod
    def _log(cls, level, msg, end="\n", flush=False):
        print(f"\033[{level}m{msg}\033[00m", end=end, flush=flush)
