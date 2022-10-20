from subprocess import Popen, PIPE
import os

from .config import get_env


def _token_tpl(h, t): return f"""
credentials "{h}" {{
    token = "{t}"
}}
"""


class TfCLI:
    stdout = None

    def __init__(self, *args, with_shell=False, stdout=False, pipefail=False):
        """Wrapper for terraform cli"""
        self.proc_args = list(args)
        self.proc: Popen[bytes] | None = None
        self.with_shell = with_shell
        self.pipefail = pipefail
        if stdout:
            self.stdout_mode = PIPE
        else:
            self.stdout_mode = None

    def __enter__(self, *_, **__):
        """Using context manager allows us to setup the cli args separately from
        running them."""

        self.proc = Popen(self._command(), shell=self.with_shell, stdout=self.stdout_mode)

        return self

    def _noshell(self):
        """Structures the subprocess command for running with no shell. This will properly 
        format the command if a pipefail flag is set."""
        command = ["terraform"] + self.proc_args
        if self.pipefail:
            command = ["/bin/bash", "-c", "set -o pipefail;"] + command
        return command

    def _withshell(self):
        """Structures the subprocess command for running with shell. This will properly
        format the command if a pipefail flag is set.

        Note: If attempting to run `self._noshell` command with a shell, the python subprocess
        will echo the environment out (bad).
        """
        command = " ".join(["terraform"] + self.proc_args)
        if self.pipefail:
            command = ["/bin/bash", "-o", "pipefail", "-c", f"'{command}'"]
        return command

    def _command(self):
        """Builds the intended command to be run"""
        return self._withshell() if self.with_shell else self._noshell()

    def __exit__(self, *_, **__):
        pass

    def __call__(self) -> int:
        if self.proc:
            stdout, _ = self.proc.communicate()
            if isinstance(stdout, bytes):
                self.stdout = stdout.decode()
            return int(self.proc.returncode)
        return 1

    @staticmethod
    def set_version(version: str | None = None) -> int:
        """Sets the terraform version in the environment.
        """

        tf_version = version or "latest"

        if tf_version == "latest":
            tf_version = "--latest"
        proc = Popen(["tfswitch", tf_version], shell=False)
        proc.communicate()

        return int(proc.returncode)

    @staticmethod
    def set_token(host: str | None = "app.terraform.io", token: str | None = None) -> int:

        if token is None:
            return 0

        with open(os.path.join(os.path.expanduser('~'), ".terraformrc"), "w") as f:
            f.write(_token_tpl(host or "app.terraform.io", token))

        print("Created .terraformrc file.")

        return 0
