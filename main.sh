#!/bin/bash

cd $WORKING_DIRECTORY

TMP_DIR=${TMP_DIR:-/app}

export FORMAT_CHECK="failure"
export INIT_CHECK="failure"
export PLAN_CHECK="failure"
export CHECKOV_CHECK="failure"
export LOG_PATH=$TMP_DIR/tfplan.log
export PLAN_PATH=$TMP_DIR/tfplan.json
export CHECKOV_PATH=$TMP_DIR/results_json.json
export APPLY_PATH=$TMP_DIR/tfapply.json
export APPLY_MARKDOWN=$TMP_DIR/SUMMARY.md

# create terraform environment
if [[ "$TF_VERSION" == "latest"  || "$TF_VERSION" == "" ]];
then
    tfswitch --latest
else
    tfswitch
fi

# setup configuration file if token is passed
if [[ "$TF_TOKEN" != "" ]];
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
    FORMAT_CHECK="success"
fi

# initialize terraform
if [[ "$TF_INIT" == "migrate" ]];
then
    terraform init -migrate-state
elif [[ "$TF_INIT" == "reconfigure" ]];
then
    terraform init -reconfigure
else
    terraform init
fi

if [[ $? == 0 ]];
then
    INIT_CHECK="success"
fi

# run plan

IFS="," read -ra ARY <<< "$TF_REPLACE"
CMDARR=("terraform" "plan" "-input=false" "-no-color" "-out" "$TMP_DIR/tfplan.binary")
for i in "${ARY[@]}"; do
    CMDARR+=( -replace="$i" )
done

# Run with xtrace
set -x;
command "${CMDARR[@]}" 2>&1 | tee $LOG_PATH
set +x;


if [[ -f "$TMP_DIR/tfplan.binary" ]];
then
    PLAN_CHECK="success"

    # convert to json
    terraform show -json -no-color $TMP_DIR/tfplan.binary | jq '.' > $PLAN_PATH
fi

# Is this a tag release?
if [[ "$GITHUB_REF_TYPE" == "tag" ]];
then
    terraform apply -auto-approve -no-color -json $TMP_DIR/tfplan.binary > $APPLY_PATH
    python3 $TMP_DIR/main.py apply

else
    if [[ -f "$TMP_DIR/tfplan.binary" ]];
    then
        # run checkov if plan was successful
        LOG_LEVEL=ERROR checkov --output-file-path $TMP_DIR -o json -f $PLAN_PATH
        # test for multiple tests
        if [[ $(cat $CHECKOV_PATH | jq -r 'type') == "object" ]];
        then
            result_array=$(cat $CHECKOV_PATH | jq  '. | [.] ')
        else
            result_array=$(cat $CHECKOV_PATH)
        fi

        if [[ $(jq '[.[] | .summary.failed ] | add' <<< $result_array) == 0 ]];
        then
            CHECKOV_CHECK="success"
        fi
    fi
    # formatted outputs
    python3 $TMP_DIR/main.py plan

    input=$APPLY_MARKDOWN
    while IFS= read -r line
    do
        echo "$line" >> $GITHUB_STEP_SUMMARY
    done < "$input"

    echo "::set-output name=fmtcheck::${FORMAT_CHECK}"
    echo "::set-output name=initcheck::${INIT_CHECK}"
    echo "::set-output name=plancheck::${PLAN_CHECK}"
    echo "::set-output name=checkovcheck::${CHECKOV_CHECK}"

    if [[ "$FORMAT_CHECK" == "failure" || "$INIT_CHECK" == "failure" || "$PLAN_CHECK" == "failure" || "$CHECKOV_CHECK" == "failure" ]];
    then
        exit 1;
    fi
fi