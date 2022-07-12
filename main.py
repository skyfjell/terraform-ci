import json
import argparse
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument('-f', '--in-file', type=str, required=True)
parser.add_argument('-o', '--out', type=str, required=True)
parser.add_argument('-t', '--type', type=str, required=True)


TF_BREAKLINE = r"─────────────────────────────────────────────────────────────────────────────"


def parse_tf_json(file):
    with open(file) as f:
        data = json.load(f)

    only_ops = [x for x in data.get("resource_changes", []) if x.get("change", {}).get("actions", []) != ["no-op"]]

    actions = {'create', 'delete', 'update'}

    report = {}
    for action in actions:
        report[action] = [x['address'] for x in only_ops if x.get("change", {}).get("actions", []) == [action]]

    report['mixed'] = [x['address'] for x in only_ops if len(x.get("change", {}).get("actions", [])) > 1]

    records = []
    for k, v in report.items():
        for r in v:
            records.append({"address": r, "action": k})

    return pd.DataFrame(records).to_markdown(index=False)


def parse_tf_log(file):
    with open(file) as f:
        raw = f.read()

    data = raw.split(TF_BREAKLINE)

    if len(data) < 2:
        return data[0]
    else:
        return data[1]


def parse_tf_checkov(file):

    with open(file) as f:
        data = json.load(f)

    records = []
    for x in data['results']['failed_checks']:
        rec = {}
        if x.get('guideline'):
            rec['check_id'] = f"[{x['check_id']}]({x.get('guideline')})"
        else:
            rec['check_id'] = x['check_id']

        rec['resource_address'] = x.get('resource_address')

        records.append(rec)

    return pd.DataFrame(records).to_markdown(index=False)


if __name__ == "__main__":
    args = parser.parse_args()

    in_file = args.in_file
    out_file = args.out
    type_ = args.type

    func = None
    if type_ == "plan":
        func = parse_tf_json
    elif type_ == "log":
        func = parse_tf_log
    elif type_ == "scan":
        func = parse_tf_checkov
    else:
        raise Exception("type can only be 'plan', 'scan', 'log'")

    with open(out_file, "w") as f:
        f.write(func(in_file))
