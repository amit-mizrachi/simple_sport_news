variable "aws_account_id" { type = string }
variable "aws_region" { type = string }
variable "environment" { type = string }
variable "project_name" { type = string }

variable "secrets_config" {
  type = map(object({
    name        = string
    description = string
  }))
  description = "Map of secret configurations. Values are set manually, not in Terraform."
}

variable "common_tags" {
  type    = map(string)
  default = {}
}
