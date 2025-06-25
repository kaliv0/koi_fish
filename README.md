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
- Describe jobs as tables/dictionaries in a config file called 'koi.toml'.
<br>(Put the config inside the root directory of your project)
```toml
[test]
description = "run tests"
dependencies = "uv sync --all-extras --dev"
commands = "uv run pytest -v --cov=./pyrio --cov-fail-under=90 --cov-report=xml"
```
- <i>description</i> and <i>dependencies</i> could be optional but not <i>commands</i>
```toml
[no-deps]
commands = "echo 'Hello world'"
```
- <i>dependencies</i> and <i>commands</i> could be strings or (in case of more than one) a list of strings
```toml
commands = ["uv run ruff check", "uv run ruff format"]
```

- You could provide a [run] table inside the config file with a <i>'suite'</i> - list of selected jobs to run
```toml
[run]
suite = ["lint", "format", "test"]
```
---------------------------
- Run the tool in the terminal with a simple <b>'koi'</b> command
```shell
$ koi
```
```shell
(logs omitted...)
$ All jobs succeeded! ['lint', 'format', 'test']
Detoxing took: 14.088007061000098
```
- In case of failing jobs you get general stats
```shell
(logs omitted...)
$ Unsuccessful detoxing took: 13.532951637999759
Failed jobs: ['format']
Successful jobs: ['lint', 'test']
```
or
```shell
$ Unsuccessful detoxing took: 8.48367640699962
Failed jobs: ['format']
Successful jobs: ['lint']
Skipped jobs: ['test']
```
---------------------------
- You could run specific jobs in the command line
```shell
$ koi --job format
```
or a list of jobs
```shell
$ koi -j format test
```
<b>NB:</b> If there is a <i>'run'</i> table in the config file jobs specified in the command line take precedence

- other available options
```shell
# run all jobs from the config file 
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
# skip a job from config file - can be combined e.g. with --run-all
$ koi -r --skip test
```
- commands showing data
```shell
# display all jobs from the config file
$ koi --all  # -a
# ['install', 'format', 'test', 'cleanup', 'run']

```
```shell
# display all jobs from the 'suite' table
$ koi --suite  # -t
# ['install', 'format', 'test']
```
```shell
# display config for a given job
$ koi --describe  format  # -d
# FORMAT
#         description: format code
#         commands: uv run ruff check
#                   uv run ruff format
```