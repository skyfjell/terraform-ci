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


def parse_tf_json(file):
    """Parses the terraform plan json output"""
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


def parse_tf_log(file):
    """Parses the terraform plan log output"""
    with open(file) as f:
        raw = f.read()

    return raw


def parse_tf_checkov(file):
    """Parses the checkov scan json output"""

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


def _read_apply_log(file):
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


def parse_tf_apply(file):
    """Parses the terraform apply json output"""

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


def parse_tf_apply_summary(file):
    """Parses the terraform apply json output"""
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


def post_plan_output(summary):
    GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]
    GITHUB_REPOSITORY_OWNER = os.environ["GITHUB_REPOSITORY_OWNER"]
    GITHUB_REPOSITORY_NAME = GITHUB_REPOSITORY.replace(GITHUB_REPOSITORY_OWNER + '/', '')
    GITHUB_REF_NAME = os.environ["GITHUB_REF_NAME"]
    GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

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


if __name__ == "__main__":

    try:
        if PLAN_CHECK != SUCCESS_ICON:
            raise Exception("Plan was not successful, see raw log.")
        plan_txt = parse_tf_json(PLAN_PATH)
    except Exception as e:
        plan_txt = "Error loading plan: " + str(e)

    try:
        summary_txt = parse_tf_log(LOG_PATH)
    except Exception as e:
        summary_txt = "Error loading summary: " + str(e)

    if sys.argv[1] == "plan":

        try:
            if PLAN_CHECK != SUCCESS_ICON:
                raise Exception("Plan was not successful, fix before running checov.")
            checkov_txt = parse_tf_checkov(CHECKOV_PATH)
        except Exception as e:
            checkov_txt = "Error loading scan: " + str(e)

        with open(APPLY_MARKDOWN, "w") as f:
            f.write(github_summary_output(
                FORMAT_CHECK,
                INIT_CHECK,
                PLAN_CHECK,
                CHECKOV_CHECK,
                plan_txt,
                summary_txt,
                checkov_txt
            ))

    elif sys.argv[1] == "apply":

        try:
            apply_text = parse_tf_apply(APPLY_PATH)

        except Exception as e:
            apply_text = "Error loading apply. Reason: " + str(e)

        # Even if tf apply failes, the output will still be in jsonl form.
        try:
            summary_apply_txt = parse_tf_apply_summary(APPLY_PATH)
        except Exception as e:
            if os.path.isfile(APPLY_PATH):
                with open(APPLY_PATH) as f:
                    summary_apply_txt = f.read()
            else:
                summary_apply_txt = "Error loading summary apply. Reason: No apply file found."

        summary = github_plan_output(
            plan_txt, summary_txt, apply_text, summary_apply_txt
        )
        return_code = post_plan_output(summary)

        print(f"::set-output name=applycheck::{return_code}")
