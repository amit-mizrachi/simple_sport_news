# ========================================================================
# SYSTEM - KEDA (Kubernetes Event-Driven Autoscaler)
# Conditional on GPU mode for content processor
# ========================================================================

resource "helm_release" "keda_release" {
  count = local.content_processor_gpu_mode ? 1 : 0

  name       = "keda"
  repository = "https://kedacore.github.io/charts"
  chart      = "keda"
  namespace  = "keda-system"
  version    = "2.14.0"

  create_namespace = true

  set {
    name  = "resources.requests.cpu"
    value = "100m"
  }
  set {
    name  = "resources.requests.memory"
    value = "128Mi"
  }
  set {
    name  = "resources.limits.cpu"
    value = "200m"
  }
  set {
    name  = "resources.limits.memory"
    value = "256Mi"
  }

  depends_on = [
    helm_release.metrics_server_release
  ]
}
