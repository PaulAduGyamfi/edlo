variable "region" {
  type    = string
  default = "us-east-1"
}
variable "environment" {
  type    = string
  default = "production"
}
variable "image_tag" {
  type    = string
  default = "bootstrap"
}
variable "domain" {
  type    = string
  default = ""
}
variable "api_desired_count" {
  type    = number
  default = 2
}
variable "github_repo" {
  type        = string
  description = "owner/repo, used to scope the OIDC trust policy"
}