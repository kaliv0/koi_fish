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
        "-S",
        "--skip",
        nargs="+",
        type=task_checker,
        default=[],
        dest="tasks_to_omit",
        metavar="TASK",
        help="skip task(s) from config file",
    )
    parser.add_argument(
        "-F",
        "--fail-fast",
        action="store_true",
        default=False,
        help="cancel flow if a task fails",
    )
    parser.add_argument(
        "--finally",
        nargs="+",
        type=task_checker,
        default=[],
        dest="tasks_to_defer",
        metavar="TASK",
        help="task(s) to run on close if the flow fails (used with --fail-fast)",
    )
    parser.add_argument(
        "-A",
        "--allow-duplicates",
        action="store_true",
        default=False,
        help="allow duplicate tasks in flow",
    )

    run_group = parser.add_mutually_exclusive_group()
    run_group.add_argument(
        "-t",
        "--tasks",
        nargs="+",
        type=task_checker,
        default=[],
        dest="cli_tasks",
        metavar="TASK",
        help="run selected task(s) from config",
    )
    run_group.add_argument(
        "-f",
        "--flow",
        dest="flow_to_run",
        metavar="FLOW",
        help="run task(s) from given 'flow' table",
    )
    run_group.add_argument(
        "-r",
        "--run-all",
        action="store_true",
        default=False,
        help="run all tasks from config",
    )

    info_group = parser.add_mutually_exclusive_group()
    info_group.add_argument(
        "-a",
        "--all",
        action="store_true",
        default=False,
        dest="display_all",
        help="display all tasks from config",
    )
    info_group.add_argument(
        "-D",
        "--describe-flow",
        dest="flow_to_describe",
        metavar="FLOW",
        help="display all tasks from given 'flow' table",
    )
    info_group.add_argument(
        "-d",
        "--describe",
        nargs="+",
        default=[],
        dest="tasks_to_describe",
        metavar="TASK",
        help="display config for given task(s)",
    )

    return parser.parse_args()


def task_checker(task: str) -> str:
    if task == Table.RUN:
        raise ArgumentTypeError(f'Invalid task: "{Table.RUN}"')
    return task


def main():
    args = get_command_line_args()
    Runner(
        args.cli_tasks,
        args.tasks_to_omit,
        args.flow_to_run,
        args.run_all,
        args.silent_logs,
        args.mute_commands,
        args.fail_fast,
        args.tasks_to_defer,
        args.allow_duplicates,
        args.display_all,
        args.tasks_to_describe,
        args.flow_to_describe,
    ).run()


if __name__ == "__main__":
    main()
