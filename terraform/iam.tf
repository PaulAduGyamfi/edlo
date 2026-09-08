data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "execution" {
  name               = "edlo-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}
resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role" "api_task" {
  name               = "edlo-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}