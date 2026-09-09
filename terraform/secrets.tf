resource "aws_secretsmanager_secret" "app" {
  name                    = "edlo/${var.environment}/app"
  recovery_window_in_days = 0 # pilot: allow immediate re-create
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DATABASE_URL = "postgresql+psycopg://edlo:${random_password.db.result}@${aws_db_instance.main.endpoint}/edlo"
  })
}

# The EXECUTION role fetches secrets (the agent injects them), not the task role.
resource "aws_iam_role_policy" "execution_secrets" {
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = aws_secretsmanager_secret.app.arn
    }]
  })
}