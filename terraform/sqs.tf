resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "edlo-jobs-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days: max, so you have time
}

resource "aws_sqs_queue" "jobs" {
  name                       = "edlo-jobs-${var.environment}"
  visibility_timeout_seconds = 300 # heartbeat extends it
  receive_wait_time_seconds  = 20  # long polling by default
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 3
  })
}

# Assumed by the WORKER's code: it receives from the queue and reads/writes S3.
resource "aws_iam_role" "worker_task" {
  name               = "edlo-worker-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

# Split by service: the API SENDS, the worker RECEIVES. The API has no
# business consuming and the worker none producing. Costs nothing, and it
# is the kind of detail a security reviewer notices.
resource "aws_iam_role_policy" "api_sqs" {
  role = aws_iam_role.api_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
      Resource = aws_sqs_queue.jobs.arn
    }]
  })
}

resource "aws_iam_role_policy" "worker_sqs" {
  role = aws_iam_role.worker_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:ReceiveMessage", "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes",
      ]
      Resource = aws_sqs_queue.jobs.arn
    }]
  })
}

# The worker downloads audio and writes transcripts: the same object policy the API has.
resource "aws_iam_role_policy" "worker_s3" {
  role   = aws_iam_role.worker_task.id
  policy = aws_iam_role_policy.api_s3.policy
}
