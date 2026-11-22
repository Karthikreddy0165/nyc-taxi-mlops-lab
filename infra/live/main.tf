# S0: Root module wiring for the NYC Taxi MLOps Lab.
#
# Modules:
#   host    EC2 Graviton instances with Docker + SSM (platform, app, llm)
#   rds     Postgres for Dagster, MLflow, and pgvector
#   bucket  CLI-managed S3 bucket for MLflow artifacts and datasets
#   secret  Secrets Manager container for lab/wiki credentials

# -----------------------------------------------------------------------------
# VPC and Subnet Data Sources (Default VPC)
# -----------------------------------------------------------------------------
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_subnet" "selected" {
  vpc_id            = data.aws_vpc.default.id
  availability_zone = var.availability_zone
}

# -----------------------------------------------------------------------------
# EC2 Hosts (contracts/runtime.yaml)
# -----------------------------------------------------------------------------

# 1. App Host (Traefik, RideApp, Model Serving, MCP)
module "host_app" {
  source             = "../modules/host"
  role               = "app"
  instance_type      = var.app_instance_type
  subnet_id          = data.aws_subnet.selected.id
  security_group_ids = [aws_security_group.app.id]
  elastic_ip         = true
}

# 2. Platform Host (Dagster Pipelines, MLflow Tracking)
module "host_platform" {
  source             = "../modules/host"
  role               = "platform"
  instance_type      = var.platform_instance_type
  subnet_id          = data.aws_subnet.selected.id
  security_group_ids = [aws_security_group.platform.id]
  elastic_ip         = true
}

# 3. LLM Host (Local LLM Chat & Embeddings)
module "host_llm" {
  source             = "../modules/host"
  role               = "llm"
  instance_type      = var.llm_instance_type
  subnet_id          = data.aws_subnet.selected.id
  security_group_ids = [aws_security_group.llm.id]
  elastic_ip         = true
}

# -----------------------------------------------------------------------------
# Managed Storage & Secrets
# -----------------------------------------------------------------------------

# Postgres Database (Dagster, MLflow, pgvector)
module "rds" {
  source             = "../modules/rds"
  instance_class     = var.rds_instance_class
  subnet_ids         = data.aws_subnets.default.ids
  security_group_ids = [aws_security_group.rds.id]
  secret_name        = "lab/rds"
}

# S3 Artifact Bucket (MLflow artifacts, training datasets)
module "bucket" {
  source = "../modules/bucket"
  name   = "lab-artifact"
}

# Secrets Manager Secret Container (lab/wiki for RAG branch in S6)
module "secret" {
  source      = "../modules/secret"
  name        = "lab/wiki"
  description = "Wiki credentials container for support assistant RAG"
}

# Secrets Manager Secret Container (lab/grafana for Alloy metrics and rules in S5)
module "secret_grafana" {
  source      = "../modules/secret"
  name        = "lab/grafana"
  description = "Grafana Cloud credentials for Alloy metrics and alerts"
}
