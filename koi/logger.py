from koi.constants import LogLevel, Font


class Logger:
    def __init__(self, no_color: bool = False) -> None:
        self.no_color = no_color

    @staticmethod
    def log(msg, end="\n", flush=False) -> None:
        print(msg, end=end, flush=flush)  # white

    def error(self, msg, end="\n", flush=False) -> None:
        self.print_log(LogLevel.ERROR, msg, end=end, flush=flush)  # red

    def success(self, msg, end="\n", flush=False) -> None:
        self.print_log(LogLevel.SUCCESS, msg, end=end, flush=flush)  # green

    def start(self, msg, end="\n", flush=False) -> None:
        self.print_log(LogLevel.START, msg, end=end, flush=flush)  # yellow

    def fail(self, msg, end="\n", flush=False) -> None:
        self.print_log(LogLevel.FAIL, msg, end=end, flush=flush)  # blue

    def debug(self, msg, end="\n", flush=False) -> None:
        self.print_log(LogLevel.DEBUG, msg, end=end, flush=flush)  # purple

    def info(self, msg, end="\n", flush=False) -> None:
        self.print_log(LogLevel.INFO, msg, end=end, flush=flush)  # light blue

    def print_log(self, level, msg, end="\n", flush=False) -> None:
        if self.no_color:
            self.log(msg, end=end, flush=flush)
        else:
            print(f"{level}{msg}{LogLevel.RESET}", end=end, flush=flush)

    @staticmethod
    def animate(msg, end="", flush=False) -> None:
        print(msg, end=end, flush=flush)

    def format_error_font(self, msg: str) -> str:
        if self.no_color:
            return f"{Font.ITALIC}{msg}{Font.RESET}"
        else:
            return f"{LogLevel.ERROR}{Font.ITALIC}{msg}{Font.RESET}{LogLevel.ERROR}"
