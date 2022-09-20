import json
import pandas as pd
import os
import sys
import requests

FAILED_ICON = "❌"
SUCCESS_ICON = "✅"
FORMAT_CHECK = "✅" if os.environ.get("FORMAT_CHECK", "failure") == "success" else "❌"
INIT_CHECK = "✅" if os.environ.get("INIT_CHECK", "failure") == "success" else "❌"
PLAN_CHECK = "✅" if os.environ.get("PLAN_CHECK", "failure") == "success" else "❌"
CHECKOV_CHECK = "✅" if os.environ.get("CHECKOV_CHECK", "failure") == "success" else "❌"
PLAN_PATH = os.environ.get("PLAN_PATH")
CHECKOV_PATH = os.environ.get("CHECKOV_PATH")
LOG_PATH = os.environ.get("LOG_PATH")
APPLY_PATH = os.environ.get("APPLY_PATH")
APPLY_MARKDOWN = os.environ.get("APPLY_MARKDOWN")

TF_BREAKLINE = r"─────────────────────────────────────────────────────────────────────────────"


def parse_tf_json(file: str) -> str:
    """This function reads the json output of the terraform plan and looks for actions that are
    either 'create', 'delete' or 'update'. Read actions labelled as 'no-op' are ignored.

    If there are multiple actions like 'create' and 'update' on a complex item such as module
    or resource with lots of blocks, we apply the label 'mix'.

    Args:
        file (str): full path to the json terraform plan output.

    Returns:
        str: A markdown formatted table of columns ['address', 'action']
    """
    with open(file) as f:
        data = json.load(f)

    # we don't care about reads
    only_ops = [x for x in data.get("resource_changes", []) if x.get("change", {}).get("actions", []) != ["no-op"]]
    actions = {'create', 'delete', 'update'}

    # single action
    report = {}
    for action in actions:
        report[action] = [x['address'] for x in only_ops if x.get("change", {}).get("actions", []) == [action]]

    # partial changes (like adding another statement to a policy)
    report['mixed'] = [x['address'] for x in only_ops if len(x.get("change", {}).get("actions", [])) > 1]

    records = []
    for k, v in report.items():
        for r in v:
            records.append({"address": r, "action": k})

    return pd.DataFrame(records).to_markdown(index=False)


def parse_tf_log(file: str) -> str:
    """Parses the terraform plan log output"""
    with open(file) as f:
        raw = f.read()

    return raw


def parse_tf_checkov(file: str) -> str:
    """This functions reads the json output of the checkov run and selects only the needed
    info from the result. Formats markdown with check_id links if existing.

    Args:
        file (str): full path to the json checkov scan output.

    Returns:
        str: A markdown formatted table of columns ['resource_address', 'check_id']
    """

    with open(file) as f:
        data = json.load(f)

    if not isinstance(data, list):
        data = [data]

    # only look in the results for failed checks
    records = []
    for check in data:
        for x in check.get('results', {}).get('failed_checks', []):
            rec = {}
            # Guideline url in its own column is pointless
            # Make the check number a link to the guideline url
            if x.get('guideline'):
                rec['check_id'] = f"[{x['check_id']}]({x.get('guideline')})"
            else:
                rec['check_id'] = x['check_id']

            # we want the full address to find it in relation to top level modules
            rec['resource_address'] = x.get('resource_address')

            records.append(rec)

    return pd.DataFrame(records).to_markdown(index=False)


def _read_apply_log(file: str) -> pd.DataFrame:
    """Parses the terraform apply log. The log is in jsonlines format,
    so we use pandas DataFrame to read it for us.

    Args:
        file (str): file path to terraform apply output.

    Returns:
        pd.DataFrame: Dataframe of each apply action.
    """
    try:
        # first attempt. Sometimes terraform likes to output stdout statements not in json format
        return pd.read_json(file, lines=True)
    except ValueError:
        # fallback method: Read line by line and ignore bad formatted json.
        lines = []
        with open(file) as f:
            for line in f.readlines():
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return pd.DataFrame(lines)


def parse_tf_apply(file: str) -> str:
    """This parases the terraform apply output and constructs a
    markdown formatted table out of the results. We filter for the 'hook' key
    in the output as address.

    Args:
        file (str): file path to terraform apply output.

    Returns:
        str: A markdown formatted table of columns ['address', 'message', 'type']
    """

    data = _read_apply_log(file)

    # If the message doesn't have a hook, it comes across here as a np.nan
    # so we just filter any non-dict types out
    if 'hook' in data.columns:
        data['hook'] = data['hook'].apply(lambda x: x if isinstance(x, dict) else {})
    else:
        # If missing hook (as in nothing was done), we just populate empty dicts
        # so the next logic step returns None
        data['hook'] = [{}] * len(data)

    ignores = ['apply_start', 'apply_progress', 'apply_errored']

    df = pd.DataFrame([{"message": x["@message"], "type": x['type'],
                      'address': x.get("hook", {}).get("resource", {}).get("addr")} for x in data.to_dict('records')])

    return df.loc[(df['address'].notna()) & (~df['type'].isin(ignores))].to_markdown(index=False)


def parse_tf_apply_summary(file: str) -> str:
    """Parses the terraform apply json output and returns the raw output."""
    data = pd.read_json(file, lines=True).to_dict('records')

    summary = [x["@message"] for x in data]

    return '\n'.join(summary)


def github_summary_output(
    fmt_check,
    init_check,
    plan_check,
    scan_check,
    plan_txt,
    summary_txt,
    checkov_txt
):
    """This creates the markdown text for github step summary
    """

    return f"""
# Step Checks

#### {fmt_check} - 🖌 Terraform Format and Style

#### {init_check} - ⚙️ Terraform Initialization

#### {plan_check} - 📖 Terraform Plan

#### {scan_check} - 🤖 Checkov Plan

# Terraform Plan

{plan_txt}

<details><summary>Plan Summary</summary>

```
{summary_txt}
```

</details>

# Checkov Scan

{checkov_txt}
"""


def github_plan_output(plan_txt, summary_txt, apply_txt, apply_summary):
    return f"""
# Terraform Plan

{plan_txt}

<details><summary>Plan Summary</summary>

```
{summary_txt}
```

</details>

# Apply Results

{apply_txt}

<details><summary>Apply Summary</summary>

```
{apply_summary}
```

</details>

    """


def post_apply_output(summary: str) -> str:
    """Takes in the summary string formatted in markdown and 
    attempts to post it to the release.

    Args:
        summary (str): Markdown formatted text.

    Returns:
        str: 'success' or 'failure'
    """

    GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]
    GITHUB_REPOSITORY_OWNER = os.environ["GITHUB_REPOSITORY_OWNER"]
    GITHUB_REPOSITORY_NAME = GITHUB_REPOSITORY.replace(GITHUB_REPOSITORY_OWNER + '/', '')
    GITHUB_REF_NAME = os.environ["GITHUB_REF_NAME"]
    GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
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
        print(f"::error::{summary}")
        return "failure"

    return "success"


def get_plan_text() -> str:
    """Returns the plan text.
    Wraps any errors for display."""
    try:
        if PLAN_CHECK != SUCCESS_ICON:
            raise Exception("Plan was not successful, see raw log.")
        return parse_tf_json(PLAN_PATH)
    except Exception as e:
        return "Error loading plan: " + str(e)


def get_summary_text() -> str:
    """Returns the summary text.
    Wraps any errors for display."""
    try:
        return parse_tf_log(LOG_PATH)
    except Exception as e:
        return "Error loading summary: " + str(e)


def get_checkov_text() -> str:
    """Returns the checkov text.
    Wraps any errors for display."""
    try:
        if PLAN_CHECK != SUCCESS_ICON:
            raise Exception("Plan was not successful, fix before running checov.")
        return parse_tf_checkov(CHECKOV_PATH)
    except Exception as e:
        return "Error loading scan: " + str(e)


def get_apply_text() -> tuple[str, str]:
    """Returns the tuple of (apply text, summary apply text).
    Wraps any errors for display."""
    try:
        apply_text = parse_tf_apply(APPLY_PATH)

    except Exception as e:
        apply_text = "Error loading apply. Reason: " + str(e)

    # Even if tf apply failes, the output will still be in jsonl form.
    try:
        summary_apply_text = parse_tf_apply_summary(APPLY_PATH)
    except Exception as e:
        if os.path.isfile(APPLY_PATH):
            with open(APPLY_PATH) as f:
                summary_apply_text = f.read()
        else:
            summary_apply_text = "Error loading summary apply. Reason: No apply file found."

    return (apply_text, summary_apply_text)


def do_plan(plan_text: str, summary_text: str) -> None:
    """Wraps all the logic for running this script in plan mode."""
    checkov_text = get_checkov_text()

    with open(APPLY_MARKDOWN, "w") as f:
        f.write(github_summary_output(
            FORMAT_CHECK,
            INIT_CHECK,
            PLAN_CHECK,
            CHECKOV_CHECK,
            plan_text,
            summary_text,
            checkov_text
        ))


def do_apply(plan_text: str, summary_text: str) -> None:
    """Wraps all the logic for running this script in apply mode."""
    (apply_text, summary_apply_text) = get_apply_text()

    summary = github_plan_output(
        plan_text, summary_text, apply_text, summary_apply_text
    )
    return_code = post_apply_output(summary)

    print(f"::set-output name=applycheck::{return_code}")


if __name__ == "__main__":
    plan_text = get_plan_text()
    summary_text = get_summary_text()

    if sys.argv[1] == "plan":
        do_plan(plan_text, summary_text)

    elif sys.argv[1] == "apply":
        do_apply(plan_text, summary_text)
