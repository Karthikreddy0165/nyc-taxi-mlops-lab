# S0: outputs listed in contracts/runtime.yaml under terraform_outputs.

output "app_public_ip" {
  description = "Public IP (Elastic IP) of the app host"
  value       = module.host_app.public_ip
}

output "app_instance_id" {
  description = "EC2 instance ID of the app host"
  value       = module.host_app.instance_id
}

output "platform_instance_id" {
  description = "EC2 instance ID of the platform host"
  value       = module.host_platform.instance_id
}

output "llm_instance_id" {
  description = "EC2 instance ID of the llm host"
  value       = module.host_llm.instance_id
}

output "rds_endpoint" {
  description = "Postgres endpoint address"
  value       = module.rds.endpoint
}

output "artifact_bucket" {
  description = "Name of the artifact bucket in S3"
  value       = module.bucket.name
}

# S1: outputs listed in contracts/platform.yaml under terraform_outputs.

output "redshift_cluster_id" {
  description = "Redshift cluster identifier"
  value       = module.redshift.cluster_id
}

output "redshift_database" {
  description = "Redshift database name"
  value       = module.redshift.database
}

# S2: SageMaker notebook
output "notebook_name" {
  description = "SageMaker notebook instance name"
  value       = module.notebook.name
}

# S3: platform private IP for serving to reach MLflow
output "platform_private_ip" {
  description = "Private IP of the platform host"
  value       = module.host_platform.private_ip
}

# S6: LLM host private IP for app and platform to reach chat and embeddings
output "llm_private_ip" {
  description = "Private IP of the LLM host"
  value       = module.host_llm.private_ip
}


