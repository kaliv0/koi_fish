import contextlib
import itertools
import os
import selectors
import signal
import subprocess
import sys
import tomllib
from collections.abc import Generator, Iterable
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from threading import Event
from typing import TypeAlias

from koi.constants import (
    CommonConfig,
    Cursor,
    ExitCode,
    LogMessages,
    Table,
    TableNames,
    TextColor,
)
from koi.logger import Logger
from koi.utils import Timer

Task: TypeAlias = list[str] | str
TaskTable: TypeAlias = dict[str, Task]
TaskPhases: TypeAlias = dict[str, list[str]]
Flow: TypeAlias = list[tuple[str, TaskTable]]


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
        display_run_table: bool,
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
        self.display_run_table = display_run_table
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
    def deferred_tasks(self) -> Flow:
        skip: Iterable[str] = (
            itertools.chain(self.successful_tasks, self.failed_tasks)
            if not self.allow_duplicates
            else ()
        )
        return self.prepare_task_flow(self.tasks_to_defer, skip)

    @cached_property
    def config_tasks(self) -> list[str]:
        return [task for task in self.data if task != Table.RUN]

    @cached_property
    def task_flow(self) -> Flow:
        if (tasks := self.resolve_task_names()) is None:
            return []
        self.all_tasks = tasks
        return self.prepare_task_flow(tasks, self.tasks_to_omit)

    def resolve_task_names(self) -> list[str] | None:
        if self.cli_tasks:
            # -t/--task flag
            return self.cli_tasks
        if self.run_all:
            # -r/--run-all
            return self.config_tasks
        if flow := self.flow_to_describe or self.flow_to_run:
            # -D or -f
            if not self.is_run_table_defined:
                self.logger.fail(
                    f"'{self.logger.format_font(Table.RUN, is_failed=True)}' table doesn't exist in the config"
                )
                return None
            return self.tasks_from_run_flow(flow)
        if self.is_run_table_defined:
            # no flag
            return self.tasks_from_run_flow(Table.MAIN)
        # no flag and no 'run/main' flow in config
        return list(self.data)

    def prepare_task_flow(self, tasks: list[str], skip: Iterable[str]) -> Flow:
        skip_set = set(skip)
        task_flow: Flow = []
        added_tasks: set[str] = set()
        for task in tasks:
            if task in skip_set or (task in added_tasks and not self.allow_duplicates):
                continue
            task_flow.append((task, self.data[task]))
            added_tasks.add(task)
        return task_flow

    @property
    def should_display_stats(self) -> bool:
        return not self.cli_tasks or len(self.cli_tasks) > 1

    @property
    def should_display_info(self) -> bool:
        # make mypy less annoying
        return (
            self.display_all
            or self.display_run_table
            or bool(self.tasks_to_describe)
            or bool(self.flow_to_describe)
        )

    @property
    def is_run_table_defined(self) -> bool:
        return Table.RUN in self.data

    @property
    def run_full_pipeline(self) -> bool:
        return not self.cli_tasks or self.run_all

    def tasks_from_run_flow(self, flow: str) -> list[str] | None:
        run_entries = self.data[Table.RUN]
        if flow not in run_entries:
            self.logger.error(
                f"Error: missing key '{self.logger.format_font(flow)}' in '{self.logger.format_font(Table.RUN)}' table"
            )
            return None
        entry = run_entries[flow]
        if not entry:
            self.logger.error(
                f"Error: '{self.logger.format_font(f'{Table.RUN} {flow}')}' cannot be empty"
            )
            return None
        if not isinstance(entry, list):
            self.logger.error(
                f"Error: '{self.logger.format_font(f'{Table.RUN} {flow}')}' must be of type list"
            )
            return None
        if Table.RUN in entry:
            self.logger.error(
                f"Error: '{self.logger.format_font(f'{Table.RUN} {flow}')}' cannot contain itself recursively"
            )
            return None
        if invalid_tasks := [task for task in entry if task not in self.data]:
            self.logger.error(
                f"Error: '{self.logger.format_font(f'{Table.RUN} {flow}')}' contains invalid tasks: {invalid_tasks}"
            )
            return None
        return entry

    ### main flow ###
    def run(self) -> None:
        signal.signal(signal.SIGTERM, signal.default_int_handler)
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
        if not os.path.getsize(config_path):
            self.logger.fail("Empty config file")
            return False
        return self.read_config_file(config_path)

    def read_config_file(self, config_path: str) -> bool:
        with open(config_path, "rb") as f:
            try:
                self.data = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                self.logger.fail(
                    f"Invalid config: {self.logger.format_font(str(e), is_failed=True)}"
                )
                return False
        if not self.data:
            self.logger.fail("Empty config file")
            return False
        return True

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
            self.logger.fail(
                f"'{self.logger.format_font(invalid_task, is_failed=True)}' not found in tasks flow"
            )
            return False
        return True

    def display_info(self) -> None:
        if self.display_all:
            self.logger.log(self.config_tasks)
        elif self.display_run_table:
            if not self.is_run_table_defined:
                self.logger.fail(
                    f"'{self.logger.format_font(Table.RUN, is_failed=True)}' table doesn't exist in the config"
                )
                return
            self.logger.info(f"{Table.RUN.upper()}:")
            self.logger.log(self.prepare_description_log(self.data[Table.RUN]))
        elif self.flow_to_describe and self.task_flow:
            self.logger.log([task for task, _ in self.task_flow])
        elif self.tasks_to_describe:
            for task in self.tasks_to_describe:
                if not (result := self.data.get(task)):
                    self.logger.fail(
                        f"Selected task '{self.logger.format_font(task, is_failed=True)}' doesn't exist in the config"
                    )
                    break
                self.logger.info(f"{task.upper()}:")
                self.logger.log(self.prepare_description_log(result))

    def prepare_description_log(self, data: TaskTable) -> str:
        if not data:
            return ""
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
                if (phases := self.build_command_phases(table, table_entries)) is None:
                    is_run_successful = False
                    if is_main_flow and self.fail_fast:
                        break
                    else:
                        continue

                is_task_successful = self.execute_shell_commands(phases, i)
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

    def get_subflow_flow(self, is_main_flow: bool) -> Flow:
        if is_main_flow:
            return self.task_flow
        return self.deferred_tasks

    def build_command_phases(self, table: str, table_entries: TaskTable) -> TaskPhases | None:
        phases: TaskPhases = {}
        for names in (Table.PRE_RUN, Table.COMMANDS, Table.POST_RUN):
            cmd, cmd_is_invalid = self.get_command(table_entries, names)
            entry_msg = f"'{self.logger.format_font('|'.join(names))}' entry in '{self.logger.format_font(table)}' table"
            if cmd_is_invalid:
                self.failed_tasks.append(table)
                self.logger.error(f"Error: duplicate {entry_msg}")
                return None
            if not cmd and names == Table.COMMANDS:
                self.failed_tasks.append(table)
                self.logger.error(f"Error: {entry_msg} cannot be empty or missing")
                return None
            if cmd:
                self.add_command(phases.setdefault(names.long, []), cmd)
        return phases

    @staticmethod
    def get_command(table_entries: TaskTable, table_names: TableNames) -> tuple[Task | None, bool]:
        cmd = None
        for name in table_names:
            if (entry := table_entries.get(name)) is not None:
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

    def execute_shell_commands(self, phases: TaskPhases, i: int) -> bool:
        if self.silent_logs:
            self.reset_event()
            with ThreadPoolExecutor(1) as executor:
                with self.shell_manager(phases):
                    executor.submit(self.spinner, i)
                    status = self.run_task_phases(phases)
            return status

        with self.shell_manager(phases):
            return self.run_task_phases(phases)

    def reset_event(self) -> None:
        if self.supervisor.is_set():
            self.supervisor.clear()

    @contextlib.contextmanager
    def shell_manager(self, phases: TaskPhases) -> Generator[None]:
        try:
            if not self.mute_commands:
                self.logger.info(
                    "\n".join(f"{name}:\n\t{'\n\t'.join(cmds)}" for name, cmds in phases.items())
                )
            yield
        except KeyboardInterrupt:
            if self.silent_logs:
                self.supervisor.set()
            self.logger.error(
                f"{Cursor.CLEAR_ANIMATION}Hey, I was in the middle of somethin' here!"
            )
            sys.exit(ExitCode.INTERRUPTED)
        finally:
            if self.silent_logs:
                # no-op if already set in except block
                self.supervisor.set()

    def spinner(self, i: int) -> None:
        animation_idx = i % len(LogMessages.ANIMATIONS)
        msg = "Keep fishin'!"
        try:
            self.logger.animate(Cursor.HIDE_CURSOR)
            for ch in itertools.cycle(LogMessages.ANIMATIONS[animation_idx]):
                self.logger.animate(f"\r{ch}\t{msg}", flush=True)
                if animation_idx > 0:
                    self.logger.animate(Cursor.MOVE_CURSOR_UP)
                if self.supervisor.wait(CommonConfig.SPINNER_TIMEOUT):
                    break
        finally:
            self.logger.animate(Cursor.CLEAR_ANIMATION)
            self.logger.animate(Cursor.SHOW_CURSOR)

    def run_task_phases(self, phases: TaskPhases) -> bool:
        ok = True
        if pre := phases.get("pre_run"):
            ok &= self.run_subprocess(pre)
        if ok:
            ok &= self.run_subprocess(phases["commands"])
        if post := phases.get("post_run"):
            # always run if present
            ok &= self.run_subprocess(post)
        return ok

    def run_subprocess(self, cmds: list[str]) -> bool:
        with self.subresource_manager(cmds) as proc:
            if self.silent_logs:
                proc.wait()
            else:
                self.stream_output(proc)
        return proc.returncode == 0

    @contextlib.contextmanager
    def subresource_manager(self, cmds: list[str]) -> Generator[subprocess.Popen[bytes]]:
        sink = subprocess.DEVNULL if self.silent_logs else subprocess.PIPE
        proc = subprocess.Popen(
            " && ".join(cmds),  # presumably every command depends on the previous one,
            stdout=sink,
            stderr=sink,
            shell=True,
            executable="/bin/bash",
            start_new_session=True,  # put shell in its own process group so we can tear-down separately on Ctrl-C
        )
        try:
            yield proc
        except BaseException:
            self.terminate_process_tree(proc)
            raise
        finally:
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()
            if proc.returncode is None:
                proc.wait()

    def stream_output(self, proc: subprocess.Popen[bytes]) -> None:
        # NB: unlike read()/communicate() read1() returns as soon as bytes are available.
        # https://docs.python.org/3/library/io.html#io.BufferedIOBase.read1
        assert proc.stdout is not None and proc.stderr is not None
        with selectors.DefaultSelector() as sel:
            sel.register(proc.stdout, selectors.EVENT_READ, self.logger.log)
            sel.register(proc.stderr, selectors.EVENT_READ, self.logger.debug)
            while sel.get_map():
                for key, _ in sel.select():
                    chunk = key.fileobj.read1()  # type: ignore[union-attr]
                    if not chunk:
                        sel.unregister(key.fileobj)
                        continue
                    key.data(chunk.decode("utf-8", errors="replace"), end="", flush=True)

    @staticmethod
    def terminate_process_tree(proc: subprocess.Popen[bytes]) -> None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=CommonConfig.TERMINATE_TIMEOUT)
        except ProcessLookupError:
            return
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
