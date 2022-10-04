import pandas as pd
import json


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
