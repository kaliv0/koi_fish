<p align="center">
  <img src="https://github.com/kaliv0/koi_fish/blob/main/assets/koi-fish.jpg?raw=true" width="450" alt="Koi fish">
</p>

# Koi fish

![Python 3.X](https://img.shields.io/badge/python-^3.12-blue?style=flat-square&logo=Python&logoColor=white)
[![PyPI](https://img.shields.io/pypi/v/koi-fish.svg)](https://pypi.org/project/koi-fish/)
[![Downloads](https://static.pepy.tech/badge/koi-fish)](https://pepy.tech/projects/koi-fish)

<br>Command line task runner & automation tool

---------------------------
### How to use
- Describe tasks as tables/dictionaries in a config file called 'koi.toml'.
<br>(Put the config inside the root directory of your project)
```toml
[test]
description = "run tests"
dependencies = "uv sync --all-extras --dev"
commands = "uv run pytest -v ."
cleanup = "rm -rf .pytest_cache/"
```
- <i>description</i>, <i>dependencies</i>  and <i>cleanup</i> could be optional but not <i>commands</i>
```toml
[no-deps]
commands = "echo 'Hello world'"
```
- <i>dependencies</i>,  <i>commands</i>  and <i>cleanup</i> could be strings or (in case of more than one) a list of strings
```toml
commands = ["uv run ruff check", "uv run ruff format"]
```

- You could provide a [run] table inside the config file with a <i>'main'</i> flow - list of selected tasks to run
```toml
[run]
main = ["lint", "format", "test"]
```
---------------------------
Example <i>koi.toml</i> (used as a main automation tool during the development of this project)
```toml
[install]
description = "setup .venv and install dependencies"
commands = "uv sync --all-extras --dev"

[format]
description = "format code"
commands = ["uv run ruff check", "uv run ruff format"]

[lint]
description = "run mypy"
commands = "uv run mypy ."

[teardown]
description = "remove venv and cache"
commands = "rm -rf .venv/ .ruff_cache/ .mypy_cache/"

[run]
description = "tasks pipeline"
flow = ["install", "format", "lint"]
```
---------------------------
- Run the tool in the terminal with a simple <b>'koi'</b> command
```shell
$ koi
```
```shell
(logs omitted...)
$ All tasks succeeded! ['lint', 'format', 'test']
Detoxing took: 14.088007061000098
```
- In case of failing tasks you get general stats
```shell
(logs omitted...)
$ Unsuccessful detoxing took: 13.532951637999759
Failed tasks: ['format']
Successful tasks: ['lint', 'test']
```
or
```shell
$ Unsuccessful detoxing took: 8.48367640699962
Failed tasks: ['format']
Successful tasks: ['lint']
Skipped tasks: ['test']
```
---------------------------
- You could run specific tasks in the command line
```shell
$ koi --task format
```
or a list of tasks
```shell
$ koi -t format test
```
<b>NB:</b> If there is a <i>'run'</i> table in the config file tasks specified in the command line take precedence

- other available options
```shell
# run all tasks from the config file 
$ koi --run-all  # short form: -r
```
```shell
# hide output logs from running commands
$ koi --silent  # -s
```
```shell
# don't print shell commands - similar to @<command> in Makefile
$ koi --mute-commands  # -m
```
```shell
# skip a task from config file - can be combined e.g. with --run-all
$ koi -r --skip test  # -S
```
- commands showing data
```shell
# display all tasks from the config file
$ koi --all  # -a
# ['install', 'format', 'test', 'cleanup', 'run']

```
```shell
# display all tasks from a flow inside 'run' table
$ koi --describe-flow  # -D
# ['install', 'format', 'test']
```
```shell
# display config for a given task
$ koi --describe  format  # -d
# FORMAT
#         description: format code
#         commands:    uv run ruff check
#                      uv run ruff format
```