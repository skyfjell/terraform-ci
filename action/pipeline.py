import os
import sys
from checkov.main import run
import json
from .terraform import TfCLI
from .utils import get_env


class ActionPipeline:

    format_result = False
    init_result = False
    plan_result = False
    scan_result = False

    def __init__(self, hard_fail=False, temp_dir: str | None = None) -> None:
        self.hard_fail = hard_fail
        self.temp_dir = temp_dir or get_env("TMP_DIR") or "/app"

    @property
    def bin_plan(self):
        """Terraform binary plan file"""
        return os.path.join(self.temp_dir, "tfplan.binary")

    @property
    def json_plan(self):
        """Terraform json plan file"""
        return os.path.join(self.temp_dir, "tfplan.json")

    @property
    def log_plan(self):
        """Terraform log plan file"""
        return os.path.join(self.temp_dir, "tfplan.log")

    @property
    def checkov(self):
        """Checkov json result file"""
        return os.path.join(self.temp_dir, "results_json.json")

    def format(self) -> "ActionPipeline":
        """Runs terraform format.

        Returns:
            ActionPipeline: Self for chaining.
        """
        with TfCLI("fmt", "-check", "-recursive") as cli:
            self.format_result = cli() == 0

        if self.hard_fail and not self.format_result:
            print("::error title=Terraform Format::Failed formatting check.")
            sys.exit(1)

        return self

    def init(self, mode: str | None = None) -> "ActionPipeline":
        """Runs the terraform init check with optional terraform mode.

         Returns:
            ActionPipeline: Self for chaining.
        """
        init_args = ["init"]

        match mode or get_env("TF_INIT"):
            case "migrate":
                init_args += ["-migrate-state"]
            case "reconfigure":
                init_args += ["-reconfigure"]
            case "upgrade":
                init_args += ["-upgrade"]
            case None:
                pass
            case _:
                print("::error title=Terraform Init::Unsupported arguement.")
                sys.exit(1)

        with TfCLI(*init_args) as cli:
            self.init_result = cli() == 0

        if self.hard_fail and not self.init_result:
            print("::error title=Terraform Init::Failed terraform init.")
            sys.exit(1)

        return self

    def plan(self, replace: list[str] = []) -> "ActionPipeline":
        """Runs terraform plan, logging out to std out as well as log file.

        Args:
            replace (list[str], optional): Replace resources list. Defaults to [].

        Returns:
            ActionPipeline: Self for chaining.
        """
        tf_args = ["plan", "-input=false", "-no-color", "-out", self.bin_plan]

        for resource in replace:
            tf_args += [f'-replace="{resource}"']

        tf_args += ["2>&1 | tee", self.log_plan]

        with TfCLI(*tf_args, with_shell=True) as cli:
            self.plan_result = cli() in [0, 2]

        if self.hard_fail and not self.plan_result:
            print("::error title=Terraform Plan::Failed terraform plan.")
            sys.exit(1)

        self._convert_plan()

        return self

    def _convert_plan(self):
        """Converts tf bin plan to json plan"""
        if not (self.plan_result and os.path.exists(self.bin_plan)):
            return
        with TfCLI("show", "-json", "-no-color", self.bin_plan, stdout=True) as cli:
            with open(self.json_plan, "w") as f:
                cli()
                json.dump(json.loads(cli.stdout), f)

    def scan(self) -> "ActionPipeline":
        if not (self.plan_result and os.path.exists(self.json_plan)):
            return self

        run(argv=["--output-file-path", self.temp_dir, "-o", "json", "-f", self.json_plan])

        return self

    def report(self) -> "ActionPipeline":

        return self

    def debug_report(self) -> "ActionPipeline":
        results = {
            "format": self.format_result,
            "init": self.init_result,
            "plan": self.plan_result,
            "scan": self.scan_result
        }
        print(results)
