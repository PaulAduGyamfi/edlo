output "alb_dns_name" { value = aws_lb.main.dns_name }
output "ecr_repository" { value = aws_ecr_repository.api.repository_url }
output "cluster_name" { value = aws_ecs_cluster.main.name }
output "private_subnets" { value = aws_subnet.private[*].id }
output "app_security_group" { value = aws_security_group.app.id }
output "cloudfront_distribution_id" { value = aws_cloudfront_distribution.web.id }
output "cloudfront_domain" { value = aws_cloudfront_distribution.web.domain_name }