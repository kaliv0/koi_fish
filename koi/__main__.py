from argparse import ArgumentParser, ArgumentTypeError, Namespace

from koi import __version__
from koi.constants import Table
from koi.runner import Runner


def get_command_line_args() -> Namespace:
    parser = ArgumentParser(
        prog="koi_fish",
        description="CLI task runner & automation tool",
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s v{__version__}")
    parser.add_argument(
        "-s",
        "--silent",
        action="store_true",
        default=False,
        dest="silent_logs",
        help="hide output logs from running commands",
    )
    parser.add_argument(
        "-m",
        "--mute-commands",
        action="store_true",
        default=False,
        help="don't print shell commands",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        type=_job_checker,
        default=[],
        dest="jobs_to_omit",
        metavar="JOBS",
        help="skip job(s) from config file",
    )

    run_group = parser.add_mutually_exclusive_group()
    run_group.add_argument(
        "-j",
        "--jobs",
        nargs="+",
        type=_job_checker,
        default=[],
        dest="cli_jobs",
        metavar="JOBS",
        help="run selected job(s) from config",
    )
    run_group.add_argument(
        "-r",
        "--run-all",
        action="store_true",
        default=False,
        help="run all jobs from config",
    )

    info_group = parser.add_mutually_exclusive_group()
    info_group.add_argument(
        "-a",
        "--all",
        action="store_true",
        default=False,
        dest="display_all",
        help="display all jobs from config",
    )
    info_group.add_argument(
        "-t",
        "--suite",
        action="store_true",
        default=False,
        dest="display_suite",
        help="display all jobs from 'suite' table",
    )
    info_group.add_argument(
        "-d",
        "--describe",
        nargs="+",
        default=[],
        dest="jobs_to_describe",
        metavar="JOBS",
        help="display config for given job(s)",
    )

    return parser.parse_args()


def _job_checker(job: str) -> str:
    if job == Table.RUN:
        raise ArgumentTypeError(f'Invalid job: "{Table.RUN}"')
    return job


def main():
    args = get_command_line_args()
    Runner(
        args.cli_jobs,
        args.jobs_to_omit,
        args.run_all,
        args.silent_logs,
        args.mute_commands,
        args.display_suite,
        args.display_all,
        args.jobs_to_describe,
    ).run()


if __name__ == "__main__":
    main()
