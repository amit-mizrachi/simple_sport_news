# ========================================================================
# SYSTEM - STRIMZI KAFKA OPERATOR
# Kafka cluster management on Kubernetes
# ========================================================================

resource "helm_release" "strimzi_operator_release" {
  name       = "strimzi-kafka-operator"
  repository = "https://strimzi.io/charts/"
  chart      = "strimzi-kafka-operator"
  namespace  = var.kafka_config.strimzi.operator_namespace
  version    = var.kafka_config.strimzi.operator_version

  create_namespace = true

  set {
    name  = "resources.requests.cpu"
    value = "200m"
  }
  set {
    name  = "resources.requests.memory"
    value = "384Mi"
  }
  set {
    name  = "resources.limits.cpu"
    value = "500m"
  }
  set {
    name  = "resources.limits.memory"
    value = "512Mi"
  }

  depends_on = [
    helm_release.metrics_server_release
  ]
}
