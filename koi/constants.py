CONFIG_FILE = "koi.toml"


class Table:
    COMMANDS = {"commands", "cmd"}
    PRE_RUN = {"pre_run", "pre"}
    POST_RUN = {"post_run", "post"}
    RUN = "run"
    MAIN = "main"


class LogLevel:
    ERROR = 91
    SUCCESS = 92
    START = 93
    FAIL = 94
    DEBUG = 95
    INFO = 96


class LogMessages:
    DELIMITER = "#########################################"
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
