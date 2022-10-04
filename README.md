# Terraform Checkov Combined Action

Runs Checkov on Terraform plans during pull requests and pretty prints output on the github summary of job runs during PRs.

## Example Plan usage

### Experimental config

Work around with yaml strings for more complex config.

```yaml
uses: skyfjell/terraform-ci@latest
with:
  config: |
    mode: plan
    workingDirectory: "."
    createRelease: false
    terraform:
      version: latest
      host: app.terraform.io
      token: "Please use env var"
      initMode: upgrade
    github:
      token: "Please use env var"
    resources:
      import:
        - address: |
            module.test["resource"] # let us format the quotes
          id: "abcd123a"
      replace:
        - ""
```

```yaml
uses: skyfjell/terraform-ci@latest
with:
  terraform_token: ${{ secrets.TF_API_TOKEN }}
```

### Produces:

<details><summary>Example Github Job Summary</summary>

# Step Checks

#### ✅ - 🖌 Terraform Format and Style

#### ✅ - ⚙️ Terraform Initialization

#### ✅ - 📖 Terraform Plan

#### ❌ - 🤖 Checkov Plan

# Terraform Plan

| address                     | action |
| :-------------------------- | :----- |
| module.something-something1 | update |
| module.something-something2 | delete |
| module.something-something3 | create |

<details><summary>Plan Summary</summary>

```
module.labels.random_string.unique_id: Refreshing state...
< RESUT OF USUAL TERRAFORM STATE REFRESH OUTPUT >

Note: Objects have changed outside of Terraform

Terraform detected the following changes made outside of Terraform since the
last "terraform apply" which may have affected this plan:

  < USUAL TERRAFORM DRIFT OUTPUT >

Unless you have made equivalent changes to your configuration, or ignored the
relevant attributes using ignore_changes, the following plan may include
actions to undo or respond to these changes.

─────────────────────────────────────────────────────────────────────────────

Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create
  ~ update in-place
  - destroy
 <= read (data resources)

Terraform will perform the following actions:

  < USUAL TERRAFORM PLAN OUTPUT >

Plan: 1 to add, 1 to change, 1 to destroy.

─────────────────────────────────────────────────────────────────────────────

Saved the plan to: /app/tfplan.binary

To perform exactly these actions, run the following command to apply:
    terraform apply "/app/tfplan.binary"
Releasing state lock. This may take a few moments...

```

</details>

# Checkov Scan

| check_id                                                                         | resource_address            |
| :------------------------------------------------------------------------------- | :-------------------------- |
| [CKV2_AWS_11](https://docs.bridgecrew.io/docs/logging_9-enable-vpc-flow-logging) | module.something-something3 |

</details>

<br />
<br />

## Example Apply (Tag) usage

Creating a tag will start this action and create a release with results in release notes.

```yaml
name: Staging Terraform Apply On Tag
on:
  push:
    tags:
      - "[0-9]+.[0-9]+.[0-9]+"
jobs:
  steps:
    - name: Checkout
      uses: actions/checkout@master
    - name: Scans, Plans and More!
      id: terraform-ci
      uses: skyfjell/terraform-ci@latest
      with:
        terraform_token: ${{ secrets.TF_API_TOKEN }}
        github_token: ${{ secrets.GITHUB_TOKEN }}
        mode: apply
```

### Produces:

<details><summary>Example Github Release Summary</summary>

# Terraform Plan

| address                     | action |
| :-------------------------- | :----- |
| module.something-something1 | create |

<details><summary>Plan Summary</summary>

```
module.labels.random_string.unique_id: Refreshing state...
< RESUT OF USUAL TERRAFORM STATE REFRESH OUTPUT >

Note: Objects have changed outside of Terraform

Terraform detected the following changes made outside of Terraform since the
last "terraform apply" which may have affected this plan:

  < USUAL TERRAFORM DRIFT OUTPUT >

Unless you have made equivalent changes to your configuration, or ignored the
relevant attributes using ignore_changes, the following plan may include
actions to undo or respond to these changes.

─────────────────────────────────────────────────────────────────────────────

Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create
  ~ update in-place
  - destroy
 <= read (data resources)

Terraform will perform the following actions:

  < USUAL TERRAFORM PLAN OUTPUT >

Plan: 1 to add, 1 to change, 1 to destroy.

─────────────────────────────────────────────────────────────────────────────

Saved the plan to: /app/tfplan.binary

To perform exactly these actions, run the following command to apply:
    terraform apply "/app/tfplan.binary"
Releasing state lock. This may take a few moments...

```

</details>

# Apply Results

| message                                                                 | type           | address                     |
| :---------------------------------------------------------------------- | :------------- | :-------------------------- |
| module.something-something1: Creation complete after 2s [id=something1] | apply_complete | module.something-something1 |

<details><summary>Apply Summary</summary>

```
{"@level":"info","@message":"Terraform 1.2.6","@module":"terraform.ui","@timestamp":"2022-08-09T00:35:03.576807Z","terraform":"1.2.6","type":"version","ui":"1.0"}
{"@level":"info","@message":"module.wf-stage.module.flux_git_repository[0].helm_release.this: Plan to create","@module":"terraform.ui","@timestamp":"2022-08-09T00:35:08.307945Z","change":{"resource":{"addr":"module.wf-stage.module.flux_git_repository[0].helm_release.this","module":"module.wf-stage.module.flux_git_repository[0]","resource":"helm_release.this","implied_provider":"helm","resource_type":"helm_release","resource_name":"this","resource_key":null},"action":"create"},"type":"planned_change"}
Releasing state lock. This may take a few moments...
{"@level":"info","@message":"Apply complete! Resources: 1 added, 0 changed, 0 destroyed.","@module":"terraform.ui","@timestamp":"2022-08-09T00:35:15.628658Z","changes":{"add":2,"change":0,"remove":0,"operation":"apply"},"type":"change_summary"}
{"@level":"info","@message":"Outputs: 0","@module":"terraform.ui","@timestamp":"2022-08-09T00:35:15.628772Z","outputs":{},"type":"outputs"}

```

</details>

</detail>
