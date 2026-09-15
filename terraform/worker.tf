resource "aws_ecr_repository" "worker" {
  name                 = "edlo-worker"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "worker" {
  repository = aws_ecr_repository.worker.name
  policy     = aws_ecr_lifecycle_policy.api.policy
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/edlo-worker"
  retention_in_days = 30
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "edlo-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024 # 1 vCPU: transcription is CPU-bound
  memory                   = 2048
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.worker_task.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([{
    name      = "worker"
    image     = "${aws_ecr_repository.worker.repository_url}:${var.image_tag}"
    essential = true
    # ECS sends SIGTERM, then SIGKILL after this. Long enough to finish a
    # transcription in flight; the lease and the idempotent handler cover the rest.
    stopTimeout = 120

    environment = [
      { name = "ENVIRONMENT", value = var.environment },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "STORAGE_BACKEND", value = "s3" },
      { name = "S3_BUCKET", value = aws_s3_bucket.media.bucket },
      { name = "S3_REGION", value = var.region },
      { name = "QUEUE_BACKEND", value = "sqs" },
      { name = "SQS_QUEUE_URL", value = aws_sqs_queue.jobs.url },
    ]
    secrets = [
      { name = "DATABASE_URL"
      valueFrom = "${aws_secretsmanager_secret.app.arn}:DATABASE_URL::" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.worker.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
}

# No load balancer: the worker pulls its work from the queue.
resource "aws_ecs_service" "worker" {
  name            = "edlo-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  lifecycle {
    ignore_changes = [task_definition, desired_count] # CI owns the image; autoscaling owns the count
  }
}

# Scale on queue depth per task, not CPU: a worker blocked on a model call
# uses no CPU while a hundred jobs pile up. The ceiling is the RDS connection
# budget (max_tasks x pool_size), which is why max_capacity is 4, not 40.
resource "aws_appautoscaling_target" "worker" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 1
  max_capacity       = 4
}

resource "aws_appautoscaling_policy" "worker_backlog" {
  name               = "edlo-worker-backlog-per-task"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.worker.service_namespace
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension

  target_tracking_scaling_policy_configuration {
    target_value       = 5
    scale_out_cooldown = 60
    scale_in_cooldown  = 300 # never kill a task mid-job on a brief lull

    customized_metric_specification {
      metrics {
        id          = "visible"
        return_data = false
        metric_stat {
          stat = "Sum"
          metric {
            namespace   = "AWS/SQS"
            metric_name = "ApproximateNumberOfMessagesVisible"
            dimensions {
              name  = "QueueName"
              value = aws_sqs_queue.jobs.name
            }
          }
        }
      }
      metrics {
        id          = "running"
        return_data = false
        metric_stat {
          stat = "Average"
          metric {
            namespace   = "ECS/ContainerInsights"
            metric_name = "RunningTaskCount"
            dimensions {
              name  = "ClusterName"
              value = aws_ecs_cluster.main.name
            }
            dimensions {
              name  = "ServiceName"
              value = aws_ecs_service.worker.name
            }
          }
        }
      }
      metrics {
        id          = "backlog_per_task"
        label       = "Visible messages per running worker"
        expression  = "visible / MAX([running, 1])"
        return_data = true
      }
    }
  }
}
