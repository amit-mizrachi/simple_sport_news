include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

dependency "sns" {
  config_path = "../sns"
  mock_outputs = {
    sns_topics = {
      content_processing = { arn = "arn:aws:sns:${include.root.locals.aws_region}:000000000000:mock-content-processing-topic" }
      query_answering    = { arn = "arn:aws:sns:${include.root.locals.aws_region}:000000000000:mock-query-answering-topic" }
    }
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "sqs" {
  config_path = "../sqs"
  mock_outputs = {
    sqs_queues = {
      content_processing = { url = "https://sqs.${include.root.locals.aws_region}.amazonaws.com/000000000000/mock-content-processing-queue" }
      query_answering    = { url = "https://sqs.${include.root.locals.aws_region}.amazonaws.com/000000000000/mock-query-answering-queue" }
    }
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

terraform {
  source = "${include.root.locals.repo_root}/deploy/iac/terraform/appconfig"
}

inputs = {
  aws_region   = include.root.inputs.aws_region
  environment  = include.root.inputs.environment
  project_name = include.root.inputs.project_name

  appconfig_config = include.root.inputs.appconfig_config

  sqs_queue_urls = {
    content_processing = dependency.sqs.outputs.sqs_queues["content_processing"].url
    query_answering    = dependency.sqs.outputs.sqs_queues["query_answering"].url
  }
  sns_topic_arns = {
    content_processing = dependency.sns.outputs.sns_topics["content_processing"].arn
    query_answering    = dependency.sns.outputs.sns_topics["query_answering"].arn
  }

  redis_host = include.root.inputs.redis_k8s_config.service_dns
  redis_port = include.root.inputs.redis_k8s_config.port

  common_tags = include.root.inputs.common_tags
}
