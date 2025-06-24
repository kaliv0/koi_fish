import argparse

from . import __version__
from .runner import Runner


def get_command_line_args():
    parser = argparse.ArgumentParser(
        prog="koi_fish",
        description="CLI automation tool",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s v{__version__}")
    parser.add_argument(
        "-j",
        "--jobs",
        nargs="+",
        help="pick a job from config file to run",
    )
    parser.add_argument(
        "-s",
        "--silent",
        action="store_true",
        help="hide logs",
    )

    parser.set_defaults(silent=False)
    return parser.parse_args()


def main():
    args = get_command_line_args()
    Runner(args.jobs, args.silent).run()


if __name__ == "__main__":
    main()
