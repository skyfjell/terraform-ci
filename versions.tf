terraform {

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0.0, < 5.0.0"
    }
    awsutils = {
      source  = "cloudposse/awsutils"
      version = ">= 0.11.0, < 1.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.2.0, < 4.0.0"
    }

  }
}


module "labels" {
  source = "skyfjell/label/null"

  name        = "wf"
  environment = "prod"
  tenant      = "main"
}
