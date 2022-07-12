#!/bin/bash

cd $WORKING_DIRECTORY

TMP_DIR=${TMP_DIR:-/app}

# create terraform environment
if [[ "$TF_VERSION" == "latest"  || "$TF_VERSION" == "" ]];
then
    tfswitch --latest
else
    tfswitch
fi

# setup configuration file if token is passed
if [[ "TF_TOKEN" != "" ]];
then
    
    cat <<EOT > ~/.terraformrc
credentials "${TF_HOST}" {
    token = "${TF_TOKEN}"
}
EOT
    
    echo "Created .terraformrc file."
    
fi

# format check
terraform fmt -check -recursive
if [[ $? == 0 ]];
then
    FORMAT_CHECK='success'
else
    FORMAT_CHECK='failure'
fi

# initialize terraform
terraform init
if [[ $? == 0 ]];
then
    INIT_CHECK='success'
else
    INIT_CHECK='failure'
fi

# run plan
terraform plan -input=false -no-color -out $TMP_DIR/tfplan.binary 2>&1 | tee $TMP_DIR/tfplan.log
if [[ $? == 0 ]];
then
    PLAN_CHECK='success'
else
    PLAN_CHECK='failure'
fi

# convert to json
terraform show -json -no-color $TMP_DIR/tfplan.binary | jq '.' > $TMP_DIR/tfplan.json

# run checkov
LOG_LEVEL=ERROR checkov --output-file-path $TMP_DIR -o json -f $TMP_DIR/tfplan.json

CHECKOV_FAILED=$(cat $TMP_DIR/results_json.json | jq '.summary | .failed')
if [[ $CHECKOV_FAILED == 0 ]];
then
    CHECKOV_CHECK='success'
else
    CHECKOV_CHECK='failure'
fi

# formatted outputs
python3 $TMP_DIR/main.py -f $TMP_DIR/tfplan.log -o $TMP_DIR/summary.txt -t log
python3 $TMP_DIR/main.py -f $TMP_DIR/results_json.json -o $TMP_DIR/checkov.md -t scan
python3 $TMP_DIR/main.py -f $TMP_DIR/tfplan.json -o $TMP_DIR/tfplan.md -t plan

PPRINTOUT=$(cat <<EOT 
### Step Checks
#### Terraform Format and Style 🖌`${FORMAT_CHECK}`
#### Terraform Initialization ⚙️`${INIT_CHECK}`
#### Terraform Plan 📖`${PLAN_CHECK}`
#### Checkov Plan 🤖`${CHECKOV_CHECK}`

### Terraform Plan

$(cat $TMP_DIR/tfplan.md)

<details><summary>Plan Summary</summary>

```
$(cat $TMP_DIR/summary.txt)
```

</details>

### Checkov Scan

$(cat $TMP_DIR/checkov.md)
EOT
)

echo "$PPRINTOUT" >> $GITHUB_STEP_SUMMARY

PPRINTOUT="${PPRINTOUT//'%'/'%25'}"
PPRINTOUT="${PPRINTOUT//$'\n'/'%0A'}"
PPRINTOUT="${PPRINTOUT//$'\r'/'%0D'}"

PLANOUT=$(cat $TMP_DIR/tfplan.md)
PLANOUT="${PLANOUT//'%'/'%25'}"
PLANOUT="${PLANOUT//$'\n'/'%0A'}"
PLANOUT="${PLANOUT//$'\r'/'%0D'}"

SUMMARYOUT=$(cat $TMP_DIR/summary.txt)
SUMMARYOUT="${SUMMARYOUT//'%'/'%25'}"
SUMMARYOUT="${SUMMARYOUT//$'\n'/'%0A'}"
SUMMARYOUT="${SUMMARYOUT//$'\r'/'%0D'}"

SCANOUT=$(cat $TMP_DIR/checkov.md)
SCANOUT="${SCANOUT//'%'/'%25'}"
SCANOUT="${SCANOUT//$'\n'/'%0A'}"
SCANOUT="${SCANOUT//$'\r'/'%0D'}"

echo "::set-output name=fmtcheck::${FORMAT_CHECK}"
echo "::set-output name=initcheck::${INIT_CHECK}"
echo "::set-output name=plancheck::${PLAN_CHECK}"
echo "::set-output name=checkovcheck::${CHECKOV_CHECK}"
echo "::set-output name=plan::${PLANOUT}"
echo "::set-output name=summary::${SUMMARYOUT}"
echo "::set-output name=scan::${SCANOUT}"
echo "::set-output name=pprint::${PPRINTOUT}"

