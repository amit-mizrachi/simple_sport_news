include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

dependency "vpc" {
  config_path = "../vpc"
  mock_outputs = {
    vpc_id         = "vpc-mock123456"
    vpc_cidr_block = "10.0.0.0/16"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

terraform {
  source = "${include.root.locals.repo_root}/deploy/iac/terraform/security-groups"
}

inputs = {
  aws_account_id = include.root.inputs.aws_account_id
  aws_region     = include.root.inputs.aws_region
  environment    = include.root.inputs.environment
  project_name   = include.root.inputs.project_name
  vpc_id         = dependency.vpc.outputs.vpc_id
  vpc_cidr_block = dependency.vpc.outputs.vpc_cidr_block
  common_tags    = include.root.inputs.common_tags
}
