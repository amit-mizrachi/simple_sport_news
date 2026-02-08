# ========================================================================
# HELM RELEASES COMMONS - SHARED LOCALS
# ========================================================================

locals {
  # Local chart paths using repo_root (absolute path from terragrunt)
  contentpulse_chart_path = "${var.repo_root}/deploy/helm/charts/contentpulse-service"

  # Common labels for all Helm releases
  common_labels = {}
}
