import itertools
import os
import subprocess
import sys
import tomllib
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import cached_property
from threading import Event
from typing import TypeAlias

from koi.constants import CommonConfig, LogMessages, Table, Cursor, TextColor
from koi.logger import Logger
from koi.utils import Timer

Task: TypeAlias = list[str] | str
TaskTable: TypeAlias = dict[str, Task]


class Runner:
    def __init__(
        self,
        dir_path: str,
        cli_tasks: list[str],
        tasks_to_omit: list[str],
        flow_to_run: str,
        run_all: bool,
        silent_logs: bool,
        mute_commands: bool,
        fail_fast: bool,
        tasks_to_defer: list[str],
        allow_duplicates: bool,
        no_color: bool,
        display_all: bool,
        tasks_to_describe: list[str],
        flow_to_describe: str,
    ) -> None:
        self.dir_path = dir_path
        self.cli_tasks = cli_tasks
        self.tasks_to_omit = tasks_to_omit
        self.flow_to_run = flow_to_run
        self.run_all = run_all
        self.silent_logs = silent_logs
        self.mute_commands = mute_commands
        self.fail_fast = fail_fast
        self.tasks_to_defer = tasks_to_defer
        self.allow_duplicates = allow_duplicates
        self.no_color = no_color
        self.display_all = display_all
        self.tasks_to_describe = tasks_to_describe
        self.flow_to_describe = flow_to_describe

        self.data: dict[str, TaskTable] = {}
        self.all_tasks: list[str] = []
        self.successful_tasks: list[str] = []
        self.failed_tasks: list[str] = []
        self.is_successful: bool = False
        # used for spinner with --silent flag
        self.supervisor = Event()

        self.logger = Logger(self.no_color)

    @cached_property
    def skipped_tasks(self) -> list[str]:
        return [
            task
            for task in self.all_tasks
            if task
            not in itertools.chain(self.successful_tasks, self.failed_tasks, self.tasks_to_omit)
        ]

    @cached_property
    def deferred_tasks(self) -> list[tuple[str, TaskTable]]:
        return self.prepare_task_flow(is_deferred=True)

    @cached_property
    def task_flow(self) -> list[tuple[str, TaskTable]]:
        if self.cli_tasks:
            # -t/--task flag
            self.all_tasks = self.cli_tasks
        elif self.run_all:
            # -r/--run-all
            self.all_tasks = [task for task in self.data if task != Table.RUN]
        elif flow := self.flow_to_describe or self.flow_to_run:
            # -D or -f
            is_successful = self.prepare_all_tasks_from_config(flow)  # noqa
            if not is_successful:
                return []
        elif Table.RUN in self.data:
            # no flag
            is_successful = self.prepare_all_tasks_from_config(Table.MAIN)
            if not is_successful:
                return []
        else:
            # no flag and no 'main' flow in config
            self.all_tasks = list(self.data)
        return self.prepare_task_flow()

    def prepare_task_flow(self, is_deferred: bool = False) -> list[tuple[str, TaskTable]]:
        tasks_list, skip_list = self.get_task_lists(is_deferred)
        task_flow = []
        added_tasks = set()
        for task in tasks_list:
            if task in skip_list or (task in added_tasks and not self.allow_duplicates):
                continue
            task_flow.append((task, self.data[task]))
            added_tasks.add(task)
        return task_flow

    def get_task_lists(self, is_deferred: bool) -> tuple[list[str], Iterable[str]]:
        if is_deferred:
            skip_list = (
                itertools.chain(self.successful_tasks, self.failed_tasks)
                if not self.allow_duplicates
                else []
            )
            return self.tasks_to_defer, skip_list
        return self.all_tasks, self.tasks_to_omit

    @property
    def should_display_stats(self) -> bool:
        return not self.cli_tasks or len(self.cli_tasks) > 1

    @property
    def should_display_info(self) -> bool:
        # make mypy less annoying
        return self.display_all or bool(self.tasks_to_describe) or bool(self.flow_to_describe)

    @property
    def run_full_pipeline(self) -> bool:
        return not self.cli_tasks or self.run_all

    def prepare_all_tasks_from_config(self, flow: str) -> bool:
        run_entries = self.data[Table.RUN]
        if flow not in run_entries:
            self.logger.error(
                f"Error: missing key '{self.logger.format_error_font(flow)}' in '{self.logger.format_error_font(Table.RUN)}' table"
            )
            return False
        if not run_entries[flow]:
            self.logger.error(
                f"Error: '{self.logger.format_error_font(f'{Table.RUN} {flow}')}' cannot be empty"
            )
            return False
        if not isinstance(run_entries[flow], list):
            self.logger.error(
                f"Error: '{self.logger.format_error_font(f'{Table.RUN} {flow}')}' must be of type list"
            )
            return False
        if Table.RUN in run_entries[flow]:
            self.logger.error(
                f"Error: '{self.logger.format_error_font(f'{Table.RUN} {flow}')}' cannot contain itself recursively"
            )
            return False
        if invalid_tasks := [task for task in run_entries[flow] if task not in self.data]:
            self.logger.error(
                f"Error: '{self.logger.format_error_font(f'{Table.RUN} {flow}')}' contains invalid tasks: {invalid_tasks}"
            )
            return False
        self.all_tasks = run_entries[flow]  # type: ignore ## 'main' is always list of str
        return True

    ### main flow ###
    def run(self) -> None:
        with Timer() as t:
            self.print_header()
            self.run_stages()
        if self.should_display_stats:
            self.log_stats(total_time=t.elapsed)

    def print_header(self) -> None:
        if not self.should_display_stats or self.should_display_info:
            return
        if self.run_full_pipeline and not self.silent_logs:
            self.logger.info(LogMessages.HEADER)
        else:
            self.logger.info("Let's go!")

    def log_stats(self, total_time: float) -> None:
        self.logger.log(LogMessages.DELIMITER)
        if self.is_successful:
            self.logger.info(f"All tasks succeeded! {self.successful_tasks}")
            self.logger.info(f"Run took: {total_time}")
            return

        self.logger.fail(f"Unsuccessful run took: {total_time}")
        if self.failed_tasks:
            # in case parsing fails before any task is run
            self.logger.error(f"Failed tasks: {self.failed_tasks}")
        if self.successful_tasks:
            self.logger.info(
                f"Successful tasks: {[x for x in self.successful_tasks if x not in self.failed_tasks]}"
            )
        if self.skipped_tasks:
            self.logger.fail(f"Skipped tasks: {self.skipped_tasks}")

    def run_stages(self) -> None:
        if not (self.handle_config_file() and self.validate_cli_tasks()):
            self.logger.fail("Run failed")
            sys.exit(1)
        if self.should_display_info:
            self.display_info()
            sys.exit()
        self.run_tasks()

    def handle_config_file(self) -> bool:
        config_path = os.path.join(self.dir_path, CommonConfig.CONFIG_FILE)
        if not os.path.exists(config_path):
            self.logger.fail("Config file not found")
            return False
        if not (os.path.getsize(config_path) and self.read_config_file(config_path)):
            self.logger.fail("Empty config file")
            return False
        return True

    def read_config_file(self, config_path: str) -> bool:
        with open(config_path, "rb") as f:
            self.data = tomllib.load(f)
        return bool(self.data)

    def validate_cli_tasks(self) -> bool:
        if not (self.cli_tasks or self.tasks_to_defer):
            return True
        if invalid_task := next(
            (
                task
                for task in set(self.cli_tasks).union(self.tasks_to_defer)
                if task not in self.data
            ),
            None,
        ):
            self.logger.fail(f"'{invalid_task}' not found in tasks flow")
            return False
        return True

    def display_info(self) -> None:
        if self.flow_to_describe:
            self.logger.log([task for task, _ in self.task_flow])
        elif self.display_all:
            self.logger.log([task for task in self.data])
        elif self.tasks_to_describe:
            for task in self.tasks_to_describe:
                if not (result := self.data.get(task)):
                    self.logger.fail(f"Selected task '{task}' doesn't exist in the config")
                    break
                self.logger.info(f"{task.upper()}:")
                self.logger.log(self.prepare_description_log(result))

    def prepare_description_log(self, data: TaskTable) -> str:
        result = []
        longest_key = max(data, key=len)
        padding = " " * (len(longest_key) + 2)
        for key, val in data.items():
            first_task_padding = " " * (len(padding) - len(key) - 1)
            if not self.no_color:
                key = f"{TextColor.YELLOW}{key}{TextColor.RESET}"
            if isinstance(val, list):
                val = f"\n\t{padding}".join(val)
            result.append(f"\t{key}:{first_task_padding}{val}")
        return "\n".join(result)

    def run_tasks(self) -> None:
        if not self.task_flow:
            return

        is_run_successful = self.run_sub_flow(is_run_successful=True, is_main_flow=True)
        if self.fail_fast and self.deferred_tasks:
            self.logger.log(LogMessages.FINALLY)
            is_run_successful = self.run_sub_flow(
                is_run_successful=is_run_successful, is_main_flow=False
            )
        self.is_successful = is_run_successful

    def run_sub_flow(self, is_run_successful: bool, is_main_flow: bool) -> bool:
        flow = self.get_subflow_flow(is_main_flow)
        for i, (table, table_entries) in enumerate(flow):
            if i > 0:
                self.logger.log(LogMessages.DELIMITER)
            self.logger.start(f"{table.upper()}:")
            with Timer() as t:
                if not (cmds := self.build_commands_list(table, table_entries)):
                    is_run_successful = False
                    if is_main_flow and self.fail_fast:
                        break
                    else:
                        continue

                is_task_successful = self.execute_shell_commands(cmds, i)
                is_run_successful &= is_task_successful
            if not is_task_successful:
                self.failed_tasks.append(table)
                self.logger.error(f"{table.upper()} failed")
                if is_main_flow and self.fail_fast:
                    break
            else:
                self.logger.success(f"{table.upper()} succeeded! Took:  {t.elapsed}")
                self.successful_tasks.append(table)
        return is_run_successful

    def get_subflow_flow(self, is_main_flow: bool) -> list[tuple[str, TaskTable]]:
        if is_main_flow:
            return self.task_flow
        return self.deferred_tasks

    def build_commands_list(self, table: str, table_entries: TaskTable) -> list[str]:
        cmds: list[str] = []
        for names in (Table.PRE_RUN, Table.COMMANDS, Table.POST_RUN):
            cmd, cmd_is_invalid = self.get_command(table_entries, names)
            entry_msg = f"'{self.logger.format_error_font('|'.join(names))}' entry in '{self.logger.format_error_font(table)}' table"
            if cmd_is_invalid:
                self.failed_tasks.append(table)
                self.logger.error(f"Error: duplicate {entry_msg}")
                return []
            if not cmd and names == Table.COMMANDS:
                self.failed_tasks.append(table)
                self.logger.error(f"Error: {entry_msg} cannot be empty or missing")
                return []
            if cmd:
                self.add_command(cmds, cmd)
        return cmds

    @staticmethod
    def get_command(table_entries: TaskTable, table_names: set[str]) -> tuple[Task | None, bool]:
        cmd = None
        for name in table_names:
            if (entry := table_entries.get(name, None)) is not None:
                if cmd:
                    return None, True
                cmd = entry
        return cmd, False

    @staticmethod
    def add_command(cmds_list: list[str], cmd: Task) -> None:
        if isinstance(cmd, list):
            cmds_list.extend(cmd)
        else:
            cmds_list.append(cmd)

    def execute_shell_commands(self, cmds: list[str], i: int) -> bool:
        if self.silent_logs:
            self.reset_event()
            with ThreadPoolExecutor(2) as executor:
                with self.shell_manager(cmds):
                    executor.submit(self.spinner, i)
                    # time.sleep(2)  # TODO
                    status = self.run_subprocess(cmds)
            return status
        else:
            with self.shell_manager(cmds):
                return self.run_subprocess(cmds)

    def reset_event(self) -> None:
        if self.supervisor.is_set():
            self.supervisor.clear()

    @contextmanager
    def shell_manager(self, cmds: list[str]):
        try:
            if not self.mute_commands:
                self.logger.info("\n".join(cmds))
            yield
        except KeyboardInterrupt:
            if self.silent_logs:
                self.supervisor.set()
            self.logger.error(
                f"{Cursor.CLEAR_ANIMATION}Hey, I was in the middle of somethin' here!"
            )
            sys.exit()
        else:
            if self.silent_logs:
                self.supervisor.set()

    def spinner(self, i: int) -> None:
        animation_idx = i % len(LogMessages.ANIMATIONS)
        msg = "Keep fishin'!"
        self.logger.animate(Cursor.HIDE_CURSOR)
        for ch in itertools.cycle(LogMessages.ANIMATIONS[animation_idx]):
            self.logger.animate(f"\r{ch}\t{msg}", flush=True)
            if animation_idx > 0:
                self.logger.animate(Cursor.MOVE_CURSOR_UP)
            if self.supervisor.wait(CommonConfig.SPINNER_TIMEOUT):
                break
        self.logger.animate(Cursor.CLEAR_ANIMATION)
        self.logger.animate(Cursor.SHOW_CURSOR)

    def run_subprocess(self, cmds: list[str]) -> bool:
        with subprocess.Popen(
            " && ".join(cmds),  # presumably every command depends on the previous one,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            executable="/bin/bash",
        ) as proc:
            if self.silent_logs:
                proc.communicate()
            else:
                # Use read1() instead of read() or Popen.communicate() as both block until EOF
                # https://docs.python.org/3/library/io.html#io.BufferedIOBase.read1
                while (text := proc.stdout.read1().decode("utf-8")) or (  # type: ignore
                    err := proc.stderr.read1().decode("utf-8")  # type: ignore
                ):
                    if text:
                        self.logger.log(text, end="", flush=True)
                    elif err:
                        self.logger.debug(err, end="", flush=True)
        return proc.returncode == 0
