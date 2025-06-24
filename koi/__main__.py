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
    # TODO: add -a/--all-jobs -> show all jobs from koi.toml with description and commands in command line
    # add -s/--show [JOB] -> similar to --all-jobs for selected job
    # add -c/--commands -> show commands when running them e.g. uv run ruff format
    #    -> or show by default without flag
    # NB: after adding more jobs -> refactor how they are passed to Runner().run
    return parser.parse_args()


def main():
    args = get_command_line_args()
    Runner().run(args.jobs)


if __name__ == "__main__":
    main()
