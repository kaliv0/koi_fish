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
    # parser.add_argument(
    #     "--no-stats",
    #     action="store_true",
    #     help="Show workflow run stats",
    # )
    # parser.set_defaults(no_stats=False)
    return parser.parse_args()


def main():
    args = get_command_line_args()
    Runner().run(args.jobs)


if __name__ == "__main__":
    main()
