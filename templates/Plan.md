# Terraform CI Action

## Step Checks

#### {{ fmt_check }} - 🖌 Terraform Format and Style

#### {{ init_check }} - ⚙️ Terraform Initialization

#### {{ plan_check }} - 📖 Terraform Plan

#### {{ scan_check }} - 🤖 Checkov Plan

## Terraform Plan

{{ plan_txt }}

<details><summary>Plan Summary</summary>

```
{{ summary_txt }}
```

</details>

## Checkov Scan

{{ checkov_txt }}

###### `terraform-ci v{{ version }}`, file bugs: {{ tracker }}
