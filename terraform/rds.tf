resource "aws_db_subnet_group" "main" {
  name       = "edlo-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
}

# Reachable ONLY from application tasks. Never the internet, never the ALB.
resource "aws_security_group" "db" {
  name   = "edlo-db"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}

resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$&*()-_=+[]{}<>?" # exclude chars that break a URL
}

resource "aws_db_instance" "main" {
  identifier     = "edlo-${var.environment}"
  engine         = "postgres"
  engine_version = "16.4"
  instance_class = "db.t4g.micro"

  allocated_storage     = 20
  max_allocated_storage = 100 # storage autoscaling
  storage_encrypted     = true

  db_name  = "edlo"
  username = "edlo"
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false # never true

  backup_retention_period         = 7
  backup_window                   = "04:00-05:00"
  maintenance_window              = "sun:05:00-sun:06:00"
  performance_insights_enabled    = true
  enabled_cloudwatch_logs_exports = ["postgresql"]

  # Pilot settings: allow clean teardown.
  deletion_protection = false
  skip_final_snapshot = true
}