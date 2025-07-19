import subprocess
from argparse import Namespace


def shell(command, **kwargs):
    command = "koi ./tests/resources " + command + " --no-color"  # TODO
    completed = subprocess.run(command, shell=True, capture_output=True, check=False, **kwargs)
    return Namespace(
        exit_code=completed.returncode,
        stdout=completed.stdout.decode().strip(),  # noqa
        stderr=completed.stderr.decode().strip(),  # noqa
    )


def test_help():
    result = shell("--help")
    assert result.exit_code == 0


def test_version():
    result = shell("--version")
    assert result.stdout == "koi_fish v1.0.2"


def test_describe():
    result = shell("-d simple")
    assert (
        result.stdout
        == """SIMPLE:
\tdescription: simple task
\tcmd:         echo 'Hello world'"""
    )


def test_task():
    result = shell("-t simple")
    assert (
        """SIMPLE:
echo 'Hello world'
Hello world
SIMPLE succeeded! Took: """
        in result.stdout
    )
