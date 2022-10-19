#!/bin/bash

python -m terraform_ci

RETURN_CODE=$?

while IFS= read -r line
do
    echo "$line" >> $GITHUB_STEP_SUMMARY
done < /app/template_result.md

echo "::debug::Python component return code is ${RETURN_CODE}"

exit $RETURN_CODE