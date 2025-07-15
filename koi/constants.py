CONFIG_FILE = "koi.toml"


class Table:
    COMMANDS = {"commands", "cmd"}
    PRE_RUN = {"pre_run", "pre"}
    POST_RUN = {"post_run", "post"}
    RUN = "run"
    MAIN = "main"


class LogLevel:
    RESET = "\033[00m"
    ERROR = "\033[91m"  # red
    SUCCESS = "\033[92m"  # green
    START = "\033[93m"  # yellow
    FAIL = "\033[94m"  # blue
    DEBUG = "\033[95m"  # purple
    INFO = "\033[96m"  # light blue


class Font:
    RESET = "\033[0m"
    # BOLD = "\033[1m"
    ITALIC = "\033[3m"
    # UNDERLINE = "\033[4m"


class TextColor:
    # same codes used in LogLevel for semantically different reason
    RESET = "\033[00m"
    YELLOW = "\033[93m"


class Cursor:
    CLEAR_LINE = "\033[2K\r"  # clear last line and put cursor at the beginning
    HIDE_CURSOR = "\033[?25l"
    SHOW_CURSOR = "\033[?25h"


class LogMessages:
    DELIMITER = "#########################################"
    FINALLY = "###########      FINALLY      ###########"
    STATES = [
        ("\\", "|", "/", "-"),
        ("▁▁▁", "▁▁▄", "▁▄█", "▄█▄", "█▄▁", "▄▁▁"),
        ("⣾", "⣷", "⣯", "⣟", "⡿", "⢿", "⣻", "⣽"),
    ]

    HEADER = r"""              ___
   ___======____=---=)
 /T            \_--===)
 [ \ (0)   \~    \_-==)
  \      / )J~~    \-=)
   \\\\___/  )JJ~~~   \)
    \_____/JJ~~~~~    \\
    / \  , \J~~~~~     \\
   (-\)\=|\\\\\~~~~       L__
   (\\\\)  (\\\\\)_           \==__
    \V    \\\\\) ===_____   \\\\\\\\\\\\
           \V)     \_) \\\\\\\\JJ\J\)
                       /J\JT\JJJJ)
                       (JJJ| \JUU)
                        (UU)'
"""
