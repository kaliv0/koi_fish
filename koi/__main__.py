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
        type=_job_checker,
        help="pick a job from config file to run",
    )
    parser.add_argument(
        "-r",
        "--run-all",
        action="store_true",
        help="run all jobs in config file",
    )
    parser.add_argument(
        "-s",
        "--silent",
        action="store_true",
        help="hide output logs from running commands",
    )
    parser.add_argument(
        "-m",
        "--mute-commands",
        action="store_true",
        help="don't print shell commands",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="display all jobs in config file",
    )
    group.add_argument(
        "-t",
        "--suite",
        action="store_true",
        help="display all jobs in 'suite' table",
    )
    group.add_argument(
        "-d",
        "--describe",
        nargs="+",
        metavar="JOBS",
        help="display config for given job",
    )

    parser.set_defaults(silent=False)
    parser.set_defaults(commands=False)
    parser.set_defaults(all=False)
    parser.set_defaults(suite=False)

    return parser.parse_args()


def _job_checker(job):
    if "run" == job:
        raise argparse.ArgumentTypeError('Invalid job: "run"')
    return job


def main():
    args = get_command_line_args()
    Runner(
        args.jobs,
        args.run_all,
        args.silent,
        args.mute_commands,
        args.suite,
        args.all,
        args.describe,
    ).run()


if __name__ == "__main__":
    main()
