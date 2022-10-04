#!/bin/bash

python -m terraform_ci

input=/app/template_result.md
while IFS= read -r line
do
    echo "$line" >> $GITHUB_STEP_SUMMARY
done < "$input"