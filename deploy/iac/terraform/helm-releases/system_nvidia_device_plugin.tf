# ========================================================================
# SYSTEM - NVIDIA DEVICE PLUGIN
# GPU resource discovery for Kubernetes, conditional on GPU enabled
# ========================================================================

resource "helm_release" "nvidia_device_plugin_release" {
  count = try(var.inference_config.content_processor.gpu_resources.enabled, false) ? 1 : 0

  name       = "nvidia-device-plugin"
  repository = "https://nvidia.github.io/k8s-device-plugin"
  chart      = "nvidia-device-plugin"
  namespace  = "kube-system"
  version    = "0.14.5"

  set {
    name  = "tolerations[0].key"
    value = "nvidia.com/gpu"
  }
  set {
    name  = "tolerations[0].operator"
    value = "Exists"
  }
  set {
    name  = "tolerations[0].effect"
    value = "NoSchedule"
  }

  depends_on = [
    helm_release.metrics_server_release
  ]
}
