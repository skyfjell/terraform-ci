import os
import sys
import json
import jinja2
import requests
from subprocess import Popen

from .parser import parse_tf_json, parse_tf_log, parse_tf_checkov, parse_tf_apply, parse_tf_apply_summary
from .terraform import TfCLI
from .config import get_env, ActionSettings
from . import __issues__, __version__


def icon(flag: bool) -> str:
    if flag:
        return "✅"
    return "❌"


class ActionPipeline:

    format_result = False
    init_result = False
    plan_result = False
    scan_result = False
    apply_result = False
    # Flag this false on a bad import
    import_result = True

    def __init__(self, settings: ActionSettings, hard_fail=False, temp_dir: str | None = None) -> None:
        self.hard_fail = hard_fail
        self.temp_dir = "/app"
        self.settings = settings

    @property
    def template_result(self):
        return os.path.join(self.temp_dir, "template_result.md")

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
    def template_dir(self):
        """Directory of templates"""
        return os.path.join(self.temp_dir, "templates")

    @property
    def apply_json(self):
        """Path to apply json"""
        return os.path.join(self.temp_dir, "tfapply.json")

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
            ret_code = cli()
            self.format_result = ret_code == 0
            print(f"::debug::Terraform fmt check result is {self.format_result} with return code {ret_code}")

        if self.hard_fail and not self.format_result:
            print("::error title=Terraform Format::Failed formatting check.")
            sys.exit(1)

        return self

    def imports(self) -> "ActionPipeline":
        """Will run terraform import on a list of resources.

        Returns:
            ActionPipeline: Self for chaining.
        """

        for resource in self.settings.resource.imports:
            with TfCLI("import", resource.address, resource.id) as cli:
                ret_code = cli()
                success = ret_code == 0
                if not success:
                    self.import_result = False
                    print(
                        f"::debug::Terraform import check result is {success} with return code {ret_code} for resource {resource.id}")

                if self.hard_fail and not success:
                    print("::error title=Terraform Import::Failed to import.")
                    sys.exit(1)

        return self

    def init(self) -> "ActionPipeline":
        """Runs the terraform init check with optional terraform mode.

        """
        init_args = ["init"]

        match self.settings.terraform.init_mode:
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
            ret_code = cli()
            self.init_result = ret_code == 0
            print(f"::debug::Terraform init check result is {self.init_result} with return code {ret_code}")

        if self.hard_fail and not self.init_result:
            print("::error title=Terraform Init::Failed terraform init.")
            sys.exit(1)

        return self

    def plan(self) -> "ActionPipeline":
        """Runs terraform plan, logging out to std out as well as log file.


        Returns:
            ActionPipeline: Self for chaining.
        """
        tf_args = ["plan", "-input=false", "-no-color", "-out", self.bin_plan]

        for resource in self.settings.resource.replace:
            tf_args += [f'-replace="{resource}"']

        tf_args += ["2>&1 | tee", self.log_plan]

        with TfCLI(*tf_args, with_shell=True, pipefail=True) as cli:
            ret_code = cli()
            self.plan_result = ret_code in [0, 2]
            print(f"::debug::Terraform plan check result is {self.plan_result} with return code {ret_code}")

        if self.hard_fail and not self.plan_result:
            print("::error title=Terraform Plan::Failed terraform plan.")
            sys.exit(1)

        self._convert_plan()

        return self

    def _convert_plan(self):
        """Converts tf bin plan to json plan"""
        if not (self.plan_result and os.path.exists(self.bin_plan)):
            print("::error title=Terraform Plan::Failed to convert terraform plan.")
            return False
        with TfCLI("show", "-json", "-no-color", self.bin_plan, stdout=True) as cli:
            with open(self.json_plan, "w") as f:
                if cli() == 0:
                    json.dump(json.loads(cli.stdout), f)
                    return True
                else:
                    print("::error title=Terraform Plan::Failed to convert terraform plan.")
                    return False

    def scan(self) -> "ActionPipeline":
        """While checkov runs on python, all implementations use it from the CLI.
        Past experiments seem to show this is still the best result even over calling it natively.
        """
        if not (self.plan_result and os.path.exists(self.json_plan)):
            return self

        proc = Popen(
            ["checkov", "--output-file-path", self.temp_dir, "-o", "json", "-f", self.json_plan],
            shell=False,
        )
        proc.communicate()
        ret_code = int(proc.returncode)
        scan_result = (ret_code == 0)

        with open(self.checkov) as f:
            result: dict | list[dict] = json.load(f)

        # sometimes we get a single object
        if not isinstance(result, list):
            result: list[dict] = [result]

        # ensure checkov ran and no failures were found
        self.scan_result = scan_result and sum(int(x.get('summary', {'failed': 0})['failed']) for x in result) == 0
        print(f"::debug::Checkov scan check result is {self.scan_result} with return code {ret_code}")

        return self

    def apply(self) -> "ActionPipeline":
        if not (self.plan_result and os.path.exists(self.json_plan)):
            print(f"::debug::Terraform apply check result could not find plan.")
            return self

        tf_args = [
            "apply", "-auto-approve", "-no-color", "-json", self.bin_plan, "2>&1 | tee", self.apply_json
        ]

        with TfCLI(*tf_args, with_shell=True, pipefail=True) as cli:
            ret_code = cli()
            self.apply_result = (ret_code in [0, 2])
            print(f"::debug::Terraform apply check result is {self.apply_result} with return code {ret_code}")

        return self

    def report(self) -> "ActionPipeline":
        plan_markdown = "Error reading plan."
        if self.plan_result and os.path.exists(self.json_plan):
            plan_markdown = parse_tf_json(self.json_plan)
        else:
            print(f"::warning title=Terraform Plan::Error reading plan.")

        log_plan = "Error reading log."
        if self.plan_result and os.path.exists(self.log_plan):
            log_plan = parse_tf_log(self.log_plan)
        else:
            print(f"::warning title=Terraform Plan::Error reading summary.")

        if self.settings.mode == "plan":
            checkov_result = "Error loading checkov results."
            if os.path.exists(self.checkov):
                checkov_result = parse_tf_checkov(self.checkov)
            else:
                print(f"::warning title=Terraform Plan::Error reading summary.")

            template = self._plan_template().render(
                fmt_check=icon(self.format_result),
                init_check=icon(self.init_result),
                plan_check=icon(self.plan_result),
                scan_check=icon(self.scan_result),
                plan_txt=plan_markdown,
                summary_txt=log_plan,
                checkov_txt=checkov_result,
                version=__version__,
                tracker=__issues__,
            )
        else:
            apply_check = "Error loading apply."
            apply_summary = "Error loading summary apply."
            # as long as json was emitted.
            if os.path.exists(self.apply_json):
                apply_check = parse_tf_apply(self.apply_json)
                apply_summary = parse_tf_apply_summary(self.apply_json)

            template = self._apply_template().render(
                plan_txt=plan_markdown,
                summary_txt=log_plan,
                apply_txt=apply_check,
                apply_summary=apply_summary,
                version=__version__,
                tracker=__issues__,
            )

            if self.settings.create_release:
                try:
                    self.post_apply_output(template)
                except Exception as e:
                    print(f"::error title=Github Post::Failed to post release because: {e}.")

        with open(self.template_result, "w") as f:
            f.write(template)

        return self

    def cleanup(self):
        """Final checks, returns exit code"""
        if self.settings.mode == "plan":
            if all([
                self.init_result,
                self.plan_result,
                self.import_result,
                self.scan_result,
            ]):
                print(f"::debug::Exiting plan mode successfully with code 0")
                sys.exit(0)

        else:
            if all([
                self.init_result,
                self.plan_result,
                self.apply_result
            ]):
                print(f"::debug::Exiting apply successfully with code 0")
                sys.exit(0)

        print(f"::debug::Exiting {self.settings.mode} unsuccessfully with code 1")
        sys.exit(1)

    def _plan_template(self):
        with open(os.path.join(self.template_dir, "Plan.md")) as f:
            return jinja2.Environment().from_string(f.read())

    def _apply_template(self):
        with open(os.path.join(self.template_dir, "Apply.md")) as f:
            return jinja2.Environment().from_string(f.read())

    def post_apply_output(self, summary: str) -> bool:
        """Takes in the summary string formatted in markdown and 
        attempts to post it to the release.

        Args:
            summary (str): Markdown formatted text.

        Returns:
            bool: success or failure
        """

        GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]
        GITHUB_REPOSITORY_OWNER = os.environ["GITHUB_REPOSITORY_OWNER"]
        GITHUB_REPOSITORY_NAME = GITHUB_REPOSITORY.replace(GITHUB_REPOSITORY_OWNER + '/', '')
        GITHUB_REF_NAME = os.environ["GITHUB_REF_NAME"]
        GITHUB_TOKEN = self.settings.github.token
        GITHUB_RUN_ID = os.environ["GITHUB_RUN_ID"]

        if len(summary) >= 125000:
            os.environ["GITHUB_STEP_SUMMARY"] = os.environ.get("GITHUB_STEP_SUMMARY", "") + summary
            summary = f"Release text too large, see plan summary from job at https://github.com/{GITHUB_REPOSITORY_NAME}/actions/runs/{GITHUB_RUN_ID}"

        response = requests.post(
            f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases",
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json"
            },
            data=json.dumps({
                "tag_name": GITHUB_REF_NAME,
                "owner": GITHUB_REPOSITORY_OWNER,
                "repo": GITHUB_REPOSITORY_NAME,
                "body": summary,
            })
        )

        # for some reason, no release is created then post as error message
        if response.status_code != 201:
            print(f"::error::could not create release because {response.text}")
            return False

        return True
