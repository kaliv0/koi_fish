import itertools
import os
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import cached_property
from itertools import chain
from threading import Event

from .logger import Logger

CONFIG_FILE = "koi.toml"
DELIMITER = "#########################################"


class Table:
    COMMANDS = "commands"
    DEPENDENCIES = "dependencies"
    RUN = "run"
    SUITE = "suite"


class Runner:
    def __init__(self, jobs, silent, log_commands, display_suite, display_all_jobs, describe_job):
        self.cli_jobs = jobs
        self.silent = silent  # TODO: rename silent_logs??
        self.log_commands = log_commands
        self.display_suite = display_suite
        self.display_all_jobs = display_all_jobs
        self.describe_job = describe_job  # TODO: rename -> job_to_describe

        self.data = {}
        self.all_jobs = []
        self.successful_jobs = []
        self.failed_jobs = []
        self.is_successful = False

        self.supervisor = None  # used for spinner with --silent flag

    @cached_property
    def skipped_jobs(self):
        return [
            job for job in self.all_jobs if job not in chain(self.failed_jobs, self.successful_jobs)
        ]

    @cached_property
    def job_suite(self):
        if self.cli_jobs:
            self._prepare_all_jobs_from_cli()
        elif Table.RUN in self.data:
            is_successful = self._prepare_all_jobs_from_config()
            if not is_successful:
                return None
        else:
            self.all_jobs = list(self.data)
        return {k: self.data[k] for k in self.all_jobs}

    def _prepare_all_jobs_from_cli(self):
        # TODO: refactor
        if Table.RUN in self.cli_jobs:
            self.all_jobs = [job for job in self.data if job != Table.RUN]
        else:
            self.all_jobs = self.cli_jobs

    def _prepare_all_jobs_from_config(self):
        jobs = dict(self.data[Table.RUN].items())
        if Table.SUITE not in jobs:
            Logger.error(f"Error: missing key '{Table.SUITE}' in '{Table.RUN}' table")
            return False
        if not jobs[Table.SUITE]:
            Logger.error(f"Error: '{Table.RUN} {Table.SUITE}' cannot be empty")
            return False
        if not isinstance(jobs[Table.SUITE], list):
            Logger.error(f"Error: '{Table.RUN} {Table.SUITE}' must be of type list")
            return False
        if Table.RUN in jobs[Table.SUITE]:
            Logger.error(f"Error: '{Table.RUN} {Table.SUITE}' cannot contain itself recursively")
            return False
        if invalid_jobs := [job for job in jobs[Table.SUITE] if job not in self.data]:
            Logger.error(
                f"Error: '{Table.RUN} {Table.SUITE}' contains invalid jobs: {invalid_jobs}"
            )
            return False
        self.all_jobs = jobs[Table.SUITE]
        return True

    ### main flow ###
    def run(self):
        global_start = time.perf_counter()
        # TODO: refactor complex bool
        if (display_stats := not self.cli_jobs or len(self.cli_jobs) > 1) and not (
            self.display_suite or self.display_all_jobs or self.describe_job
        ):
            Logger.info("Let's go!")

        self._run_stages()
        global_stop = time.perf_counter()
        if display_stats:
            self._log_stats(total_time=(global_stop - global_start))

    def _log_stats(self, total_time):
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

    def _run_stages(self):
        if not (self._handle_config_file() and self._validate_cli_jobs()):
            Logger.fail("Run failed")
            sys.exit(1)

        # TODO: extract as separate stage
        if self.display_suite:
            Logger.log([job for job in self.job_suite])
            sys.exit()

        if self.display_all_jobs:
            Logger.log([job for job in self.data])
            sys.exit()

        if self.describe_job:
            for job in self.describe_job:
                if not (result := self.data.get(job)):
                    Logger.fail(f"Selected job '{job}' doesn't exist in the config")
                    sys.exit()
                Logger.info(f"{job.upper():}")
                # TODO: cleanup mess
                Logger.log(
                    "\n".join(
                        f"\t\033[93m{k}\033[00m: {f'\n\t{" " * (len(Table.COMMANDS) + 2)}'.join(v) if isinstance(v, list) else v}"
                        for k, v in result.items()
                    )
                )
            sys.exit()

        self._run_jobs()

    def _handle_config_file(self):
        config_path = os.path.join(os.getcwd(), CONFIG_FILE)
        if not os.path.exists(config_path):
            Logger.fail("Config file not found")
            return False
        if not os.path.getsize(config_path):
            Logger.fail("Empty config file")
            return False
        return self._read_config_file(config_path)

    def _read_config_file(self, config_path):
        with open(config_path, "rb") as f:
            self.data = tomllib.load(f)
        return bool(self.data)

    def _validate_cli_jobs(self):
        if not self.cli_jobs:
            return True
        if invalid_job := next((job for job in self.cli_jobs if job not in self.data), None):
            Logger.fail(f"'{invalid_job}' not found in jobs suite")
            return False
        return True

    def _run_jobs(self):
        if not self.job_suite:
            # TODO:
            # return False
            self.is_successful = False
            return

        is_run_successful = True
        # TODO: rename i
        for i, (table, table_entries) in enumerate(self.job_suite.items()):
            Logger.log(DELIMITER)
            Logger.start(f"{table.upper()}:")
            start = time.perf_counter()

            install = self._build_install_command(table_entries)
            if not (run := self._build_run_command(table, table_entries)):
                return False

            # NB: add more steps here e.g. teardown after run
            cmds = []
            if install:
                cmds.append(install)
            cmds.append(run)

            if not (is_job_successful := self._execute_shell_commands(" && ".join(cmds), i)):
                self.failed_jobs.append(table)
                Logger.error(f"{table.upper()} failed")
            else:
                stop = time.perf_counter()
                Logger.success(f"{table.upper()} succeeded! Took:  {stop - start}")
                self.successful_jobs.append(table)
            is_run_successful &= is_job_successful

        self.is_successful = is_run_successful
        Logger.log(DELIMITER)

    # build shell commands
    @staticmethod
    def _build_install_command(table_entries):
        if not (deps := table_entries.get(Table.DEPENDENCIES, None)):
            return None
        return " && ".join(deps) if isinstance(deps, list) else deps

    def _build_run_command(self, table, table_entries):
        if not (cmds := table_entries.get(Table.COMMANDS, None)):
            self.failed_jobs.append(table)
            Logger.error(f"Error: '{Table.COMMANDS}' in '{table}' table cannot be empty or missing")
            return None
        return " && ".join(cmds) if isinstance(cmds, list) else cmds

    def _execute_shell_commands(self, run, i):
        if self.silent:
            self.supervisor = Event()
            with ThreadPoolExecutor(2) as executor:
                with self._try(run):
                    executor.submit(self._spinner, i)
                    time.sleep(5)  # TODO
                    status = self._run_subprocess(run)
            return status
        else:
            with self._try(run):
                return self._run_subprocess(run)

    @contextmanager
    def _try(self, run):  # TODO: rename
        try:
            # TODO: should we log here?
            if self.log_commands:
                Logger.info(run)
            yield
        except KeyboardInterrupt:
            if self.silent:
                self.supervisor.set()
            Logger.error("\033[2K\rHey, I was in the middle of something here!")
            sys.exit()
        else:
            if self.silent:
                self.supervisor.set()

    def _spinner(self, i):
        # TODO: extract consts
        states = [
            ("\\", "|", "/", "-"),
            ("▁▁▁", "▁▁▄", "▁▄█", "▄█▄", "█▄▁", "▄▁▁"),
            ("⣾", "⣷", "⣯", "⣟", "⡿", "⢿", "⣻", "⣽"),
        ]
        msg = "Keep fishin'!"

        print("\033[?25l", end="")  # hide blinking cursor
        for ch in itertools.cycle(states[i % 3]):
            print(f"\r{ch} {msg} {ch}", end="", flush=True)
            if self.supervisor.wait(0.1):
                break
        print("\033[2K\r", end="")  # clear last line and put cursor at the begining
        print("\033[?25h", end="")  # make cursor visible

    def _run_subprocess(self, run):
        with subprocess.Popen(
            run, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, executable="/bin/bash"
        ) as proc:
            if self.silent:
                proc.communicate()
            else:
                # Use read1() instead of read() or Popen.communicate() as both block until EOF
                # https://docs.python.org/3/library/io.html#io.BufferedIOBase.read1
                while (text := proc.stdout.read1().decode("utf-8")) or (
                    err := proc.stderr.read1().decode("utf-8")
                ):
                    if text:
                        Logger.log(text, end="", flush=True)
                    elif err:
                        Logger.debug(err, end="", flush=True)
        return proc.returncode == 0
