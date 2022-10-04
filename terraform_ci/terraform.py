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

    def __init__(self, *args, with_shell=False, stdout=False):
        """Wrapper for terraform cli"""
        self.proc_args = list(args)
        self.proc: Popen[bytes] | None = None
        self.with_shell = with_shell
        if stdout:
            self.stdout_mode = PIPE
        else:
            self.stdout_mode = None

    def __enter__(self, *_, **__):
        """Using context manager allows us to setup the cli args separately from
        running them."""
        if self.with_shell:
            cmd = " ".join(["terraform"] + self.proc_args)
            self.proc = Popen(cmd, shell=True, stdout=self.stdout_mode)
        else:
            cmd = ["terraform"] + self.proc_args
            self.proc = Popen(cmd, shell=False, stdout=self.stdout_mode)
        return self

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
        """Sets the terraform version in the environment. Will fall back to 
        env var `TF_VERSION`.
        """

        tf_version = get_env("TF_VERSION") or version or "latest"

        if tf_version == "latest":
            tf_version = "--latest"
        proc = Popen(["tfswitch", tf_version], shell=False)
        proc.communicate()

        return int(proc.returncode)

    @staticmethod
    def set_token(host: str | None = "app.terraform.io", token: str | None = None) -> int:

        tf_host = host or get_env("TF_TOKEN") or "app.terraform.io"
        tf_token = token or get_env("TF_TOKEN")
        if tf_token is None:
            return 0

        with open(os.path.join(os.path.expanduser('~'), ".terraformrc"), "w") as f:
            f.write(_token_tpl(tf_host, tf_token))

        print("Created .terraformrc file.")

        return 0
