# S0: security groups and rules following contracts/runtime.yaml.
#
# Decision point: ingress scope for the app host (Traefik, port 80).
# Recorded in decisions/ with rationale: Traefik serves public riders.
#
# Traffic between hosts:
#   app -> platform        MLflow (port 5000)
#   app, platform -> llm   chat (8080) and embeddings (8081)
#   app, platform -> rds   Postgres (5432)
# No SSH / port 22: shell access is SSM Session Manager; UIs use SSM port-forwarding.

# -----------------------------------------------------------------------------
# 1. App Host Security Group (Traefik, App, Serving, MCP)
# -----------------------------------------------------------------------------
resource "aws_security_group" "app" {
  name        = "lab-app"
  description = "App host: Traefik on port 80, backend microservices"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "lab-app-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "app_http" {
  for_each          = toset(var.ingress_cidrs)
  security_group_id = aws_security_group.app.id
  description       = "HTTP to Traefik reverse proxy"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = each.value
}

resource "aws_vpc_security_group_egress_rule" "app_egress" {
  security_group_id = aws_security_group.app.id
  description       = "Allow all outbound traffic"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# -----------------------------------------------------------------------------
# 2. Platform Host Security Group (Dagster, MLflow)
# -----------------------------------------------------------------------------
resource "aws_security_group" "platform" {
  name        = "lab-platform"
  description = "Platform host: MLflow tracking and Dagster orchestrator"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "lab-platform-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "platform_mlflow_from_app" {
  security_group_id            = aws_security_group.platform.id
  description                  = "MLflow tracking from app host"
  ip_protocol                  = "tcp"
  from_port                    = 5000
  to_port                      = 5000
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_ingress_rule" "platform_mlflow_from_self" {
  security_group_id            = aws_security_group.platform.id
  description                  = "MLflow tracking from platform pipelines"
  ip_protocol                  = "tcp"
  from_port                    = 5000
  to_port                      = 5000
  referenced_security_group_id = aws_security_group.platform.id
}

resource "aws_vpc_security_group_ingress_rule" "platform_mlflow_from_notebook" {
  security_group_id            = aws_security_group.platform.id
  description                  = "MLflow tracking from SageMaker notebook"
  ip_protocol                  = "tcp"
  from_port                    = 5000
  to_port                      = 5000
  referenced_security_group_id = module.notebook.security_group_id
}

resource "aws_vpc_security_group_egress_rule" "platform_egress" {
  security_group_id = aws_security_group.platform.id
  description       = "Allow all outbound traffic"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# -----------------------------------------------------------------------------
# 3. LLM Host Security Group (Ollama / vLLM chat & embeddings)
# -----------------------------------------------------------------------------
resource "aws_security_group" "llm" {
  name        = "lab-llm"
  description = "LLM host: local chat (8080) and embeddings (8081)"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "lab-llm-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "llm_chat_from_app" {
  security_group_id            = aws_security_group.llm.id
  description                  = "LLM chat from app host"
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_ingress_rule" "llm_chat_from_platform" {
  security_group_id            = aws_security_group.llm.id
  description                  = "LLM chat from platform pipelines"
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
  referenced_security_group_id = aws_security_group.platform.id
}

resource "aws_vpc_security_group_ingress_rule" "llm_embed_from_app" {
  security_group_id            = aws_security_group.llm.id
  description                  = "LLM embeddings from app host"
  ip_protocol                  = "tcp"
  from_port                    = 8081
  to_port                      = 8081
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_ingress_rule" "llm_embed_from_platform" {
  security_group_id            = aws_security_group.llm.id
  description                  = "LLM embeddings from platform pipelines"
  ip_protocol                  = "tcp"
  from_port                    = 8081
  to_port                      = 8081
  referenced_security_group_id = aws_security_group.platform.id
}

resource "aws_vpc_security_group_egress_rule" "llm_egress" {
  security_group_id = aws_security_group.llm.id
  description       = "Allow all outbound traffic"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# -----------------------------------------------------------------------------
# 4. RDS Postgres Security Group
# -----------------------------------------------------------------------------
resource "aws_security_group" "rds" {
  name        = "lab-rds"
  description = "Postgres RDS: Dagster, MLflow, and pgvector storage"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "lab-rds-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_app" {
  security_group_id            = aws_security_group.rds.id
  description                  = "Postgres access from app host"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_platform" {
  security_group_id            = aws_security_group.rds.id
  description                  = "Postgres access from platform host"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.platform.id
}

resource "aws_vpc_security_group_egress_rule" "rds_egress" {
  security_group_id = aws_security_group.rds.id
  description       = "Allow all outbound traffic"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}