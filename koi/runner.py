import itertools
import os
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import cached_property
from threading import Event
from typing import TypeAlias

from koi.constants import CommonConfig, LogMessages, Table, Cursor, TextColor
from koi.logger import Logger

Job: TypeAlias = list[str] | str
JobTable: TypeAlias = dict[str, Job]


class Runner:
    def __init__(
        self,
        cli_jobs: list[str],
        jobs_to_omit: list[str],
        run_all: bool,
        silent_logs: bool,
        mute_commands: bool,
        fail_fast: bool,
        jobs_to_defer: list[str],
        allow_duplicates: bool,
        display_suite: bool,
        display_all: bool,
        jobs_to_describe: list[str],
    ) -> None:
        self.cli_jobs = cli_jobs
        self.jobs_to_omit = jobs_to_omit
        self.run_all = run_all
        self.silent_logs = silent_logs
        self.mute_commands = mute_commands
        self.fail_fast = fail_fast
        self.jobs_to_defer = jobs_to_defer
        self.allow_duplicates = allow_duplicates
        self.display_suite = display_suite
        self.display_all = display_all
        self.jobs_to_describe = jobs_to_describe

        self.data: dict[str, JobTable] = {}
        self.all_jobs: list[str] = []
        self.successful_jobs: list[str] = []
        self.failed_jobs: list[str] = []
        self.is_successful: bool = False
        # used for spinner with --silent flag
        self.supervisor = Event()

    @cached_property
    def skipped_jobs(self) -> list[str]:
        return [
            job
            for job in self.all_jobs
            if job not in itertools.chain(self.successful_jobs, self.failed_jobs, self.jobs_to_omit)
        ]

    @cached_property
    def deferred_jobs(self) -> list[tuple[str, JobTable]]:
        return self.prepare_job_suite(is_deferred=True)

    @cached_property
    def job_suite(self) -> list[tuple[str, JobTable]]:
        if self.cli_jobs:
            self.all_jobs = self.cli_jobs
        elif self.run_all:
            self.all_jobs = [job for job in self.data if job != Table.RUN]
        elif Table.RUN in self.data:
            is_successful = self.prepare_all_jobs_from_config()
            if not is_successful:
                return []
        else:
            self.all_jobs = list(self.data)
        return self.prepare_job_suite()

    def prepare_job_suite(self, is_deferred: bool = False) -> list[tuple[str, JobTable]]:
        jobs_list, skip_list = self.get_job_lists(is_deferred)
        job_suite = []
        added_jobs = set()
        for job in jobs_list:
            if job in skip_list or (job in added_jobs and not self.allow_duplicates):
                continue
            job_suite.append((job, self.data[job]))
            added_jobs.add(job)
        return job_suite

    def get_job_lists(
        self, is_deferred: bool
    ) -> tuple[list[str], list[str] | itertools.chain[str]]:
        if is_deferred:
            return self.jobs_to_defer, itertools.chain(self.successful_jobs, self.failed_jobs)
        return self.all_jobs, self.jobs_to_omit

    @property
    def should_display_stats(self) -> bool:
        return not self.cli_jobs or len(self.cli_jobs) > 1

    @property
    def should_display_job_info(self) -> bool:
        return self.display_suite or self.display_all or bool(self.jobs_to_describe)

    @property
    def run_full_pipeline(self) -> bool:
        return not self.cli_jobs or self.run_all

    def prepare_all_jobs_from_config(self) -> bool:
        jobs = self.data[Table.RUN]
        if Table.MAIN not in jobs:
            Logger.error(
                f"Error: missing key '{Logger.format_error_font(Table.MAIN)}' in '{Logger.format_error_font(Table.RUN)}' table"
            )
            return False
        if not jobs[Table.MAIN]:
            Logger.error(
                f"Error: '{Logger.format_error_font(f'{Table.RUN} {Table.MAIN}')}' cannot be empty"
            )
            return False
        if not isinstance(jobs[Table.MAIN], list):
            Logger.error(
                f"Error: '{Logger.format_error_font(f'{Table.RUN} {Table.MAIN}')}' must be of type list"
            )
            return False
        if Table.RUN in jobs[Table.MAIN]:
            Logger.error(
                f"Error: '{Logger.format_error_font(f'{Table.RUN} {Table.MAIN}')}' cannot contain itself recursively"
            )
            return False
        if invalid_jobs := [job for job in jobs[Table.MAIN] if job not in self.data]:
            Logger.error(
                f"Error: '{Logger.format_error_font(f'{Table.RUN} {Table.MAIN}')}' contains invalid jobs: {invalid_jobs}"
            )
            return False
        self.all_jobs = jobs[Table.MAIN]  # type: ignore ## 'main' is always list of str
        return True

    ### main flow ###
    def run(self) -> None:
        global_start = time.perf_counter()
        self.print_header()
        self.run_stages()
        global_stop = time.perf_counter()
        if self.should_display_stats:
            self.log_stats(total_time=(global_stop - global_start))

    def print_header(self) -> None:
        if not self.should_display_stats or self.should_display_job_info:
            return
        if self.run_full_pipeline and not self.silent_logs:
            Logger.info(LogMessages.HEADER)
        else:
            Logger.info("Let's go!")

    def log_stats(self, total_time: float) -> None:
        Logger.log(LogMessages.DELIMITER)
        if self.is_successful:
            Logger.info(f"All jobs succeeded! {self.successful_jobs}")
            Logger.info(f"Run took: {total_time}")
            return

        Logger.fail(f"Unsuccessful run took: {total_time}")
        if self.failed_jobs:
            # in case parsing fails before any job is run
            Logger.error(f"Failed jobs: {self.failed_jobs}")
        if self.successful_jobs:
            Logger.info(
                f"Successful jobs: {[x for x in self.successful_jobs if x not in self.failed_jobs]}"
            )
        if self.skipped_jobs:
            Logger.fail(f"Skipped jobs: {self.skipped_jobs}")

    def run_stages(self) -> None:
        if not (self.handle_config_file() and self.validate_cli_jobs()):
            Logger.fail("Run failed")
            sys.exit(1)
        if self.display_suite or self.display_all or self.jobs_to_describe:
            self.display_jobs_info()
            sys.exit()
        self.run_jobs()

    def handle_config_file(self) -> bool:
        config_path = os.path.join(os.getcwd(), CommonConfig.CONFIG_FILE)
        if not os.path.exists(config_path):
            Logger.fail("Config file not found")
            return False
        if not os.path.getsize(config_path):
            Logger.fail("Empty config file")
            return False
        return self.read_config_file(config_path)

    def read_config_file(self, config_path: str) -> bool:
        with open(config_path, "rb") as f:
            self.data = tomllib.load(f)
        return bool(self.data)

    def validate_cli_jobs(self) -> bool:
        if not (self.cli_jobs or self.jobs_to_defer):
            return True
        if invalid_job := next(
            (job for job in set(self.cli_jobs).union(self.jobs_to_defer) if job not in self.data),
            None,
        ):
            Logger.fail(f"'{invalid_job}' not found in jobs suite")
            return False
        return True

    def display_jobs_info(self) -> None:
        if self.display_suite:
            Logger.log([job for job, _ in self.job_suite])
        elif self.display_all:
            Logger.log([job for job in self.data])
        elif self.jobs_to_describe:
            for job in self.jobs_to_describe:
                if not (result := self.data.get(job)):
                    Logger.fail(f"Selected job '{job}' doesn't exist in the config")
                    break
                Logger.info(f"{job.upper()}:")
                Logger.log(self.prepare_description_log(result))

    @staticmethod
    def prepare_description_log(data: JobTable) -> str:
        result = []
        for key, val in data.items():
            colored_key = f"\t{TextColor.YELLOW}{key}{TextColor.RESET}"
            if isinstance(val, list):
                padding = " " * (len(key) + 2)
                val = f"\n\t{padding}".join(val)
            result.append(f"{colored_key}: {val}")
        return "\n".join(result)

    def run_jobs(self) -> None:
        if not self.job_suite:
            return

        is_run_successful = self.run_sub_flow(is_run_successful=True, is_main_flow=True)
        if self.fail_fast and self.deferred_jobs:
            Logger.log(LogMessages.FINALLY)
            is_run_successful = self.run_sub_flow(
                is_run_successful=is_run_successful, is_main_flow=False
            )
        self.is_successful = is_run_successful

    def run_sub_flow(self, is_run_successful: bool, is_main_flow: bool) -> bool:
        suite = self.get_subflow_suite(is_main_flow)
        for i, (table, table_entries) in enumerate(suite):
            if i > 0:
                Logger.log(LogMessages.DELIMITER)
            Logger.start(f"{table.upper()}:")
            start = time.perf_counter()

            if not (cmds := self.build_commands_list(table, table_entries)):
                is_run_successful = False
                if is_main_flow and self.fail_fast:
                    break
                else:
                    continue

            is_job_successful = self.execute_shell_commands(cmds, i)
            is_run_successful &= is_job_successful
            if not is_job_successful:
                self.failed_jobs.append(table)
                Logger.error(f"{table.upper()} failed")
                if is_main_flow and self.fail_fast:
                    break
            else:
                stop = time.perf_counter()
                Logger.success(f"{table.upper()} succeeded! Took:  {stop - start}")
                self.successful_jobs.append(table)
        return is_run_successful

    def get_subflow_suite(self, is_main_flow: bool) -> list[tuple[str, JobTable]]:
        if is_main_flow:
            return self.job_suite
        return self.deferred_jobs

    def build_commands_list(self, table: str, table_entries: JobTable) -> list[str]:
        cmds: list[str] = []
        for names in (Table.PRE_RUN, Table.COMMANDS, Table.POST_RUN):
            cmd, cmd_is_invalid = self.get_command(table_entries, names)
            entry_msg = f"'{Logger.format_error_font('|'.join(names))}' entry in '{Logger.format_error_font(table)}' table"
            if cmd_is_invalid:
                self.failed_jobs.append(table)
                Logger.error(f"Error: duplicate {entry_msg}")
                return []
            if not cmd and names == Table.COMMANDS:
                self.failed_jobs.append(table)
                Logger.error(f"Error: {entry_msg} cannot be empty or missing")
                return []
            if cmd:
                self.add_command(cmds, cmd)
        return cmds

    @staticmethod
    def get_command(table_entries: JobTable, table_names: set[str]) -> tuple[Job | None, bool]:
        cmd = None
        for name in table_names:
            if (entry := table_entries.get(name, None)) is not None:
                if cmd:
                    return None, True
                cmd = entry
        return cmd, False

    @staticmethod
    def add_command(cmds_list: list[str], cmd: Job) -> None:
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
                    time.sleep(7)  # TODO
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
                Logger.info("\n".join(cmds))
            yield
        except KeyboardInterrupt:
            if self.silent_logs:
                self.supervisor.set()
            Logger.error(f"{Cursor.CLEAR_ANIMATION}Hey, I was in the middle of somethin' here!")
            sys.exit()
        else:
            if self.silent_logs:
                self.supervisor.set()

    def spinner(self, i: int) -> None:
        animation_idx = i % len(LogMessages.ANIMATIONS)
        msg = "Keep fishin'!"
        Logger.animate(Cursor.HIDE_CURSOR)
        for ch in itertools.cycle(LogMessages.ANIMATIONS[animation_idx]):
            Logger.animate(f"\r{ch}\t{msg}", flush=True)
            if animation_idx > 0:
                Logger.animate(Cursor.MOVE_CURSOR_UP)
            if self.supervisor.wait(CommonConfig.SPINNER_TIMEOUT):
                break
        Logger.animate(Cursor.CLEAR_ANIMATION)
        Logger.animate(Cursor.SHOW_CURSOR)

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
                        Logger.log(text, end="", flush=True)
                    elif err:
                        Logger.debug(err, end="", flush=True)
        return proc.returncode == 0
