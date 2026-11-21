# S2: wire infra/modules/notebook (the SageMaker notebook) into this root module, let it reach MLflow
# on the platform host (port 5000, runtime.yaml), and output its name as notebook_name.
# Set github_repo in terraform.tfvars: the notebook clones your public repo.

module "notebook" {
  source = "../modules/notebook"

  name      = "lab"
  subnet_id = data.aws_subnet.selected.id
  repo_url  = "https://github.com/${var.github_repo}"

  env = {
    MLFLOW_TRACKING_URI = "http://${module.host_platform.private_ip}:5000"
    REDSHIFT_CLUSTER_ID = module.redshift.cluster_id
    REDSHIFT_DATABASE   = module.redshift.database
    REDSHIFT_DB_USER    = module.redshift.admin_user
  }
}

