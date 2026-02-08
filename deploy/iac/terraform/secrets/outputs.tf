output "secrets" {
  description = "Map of secrets with standardized output structure"
  value = {
    for key, secret in aws_secretsmanager_secret.secrets : key => {
      arn  = secret.arn
      id   = secret.id
      name = secret.name
    }
  }
}
