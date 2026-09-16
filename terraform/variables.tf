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
  description = "The repo portion of the OIDC subject claim, including GitHub's numeric owner and repo IDs (e.g. owner@123/repo@456). Decode the token in a workflow run to find it."
}

# Supply at apply time: `TF_VAR_model_api_key=sk-ant-... terraform apply`.
# Never put it in a tfvars file. Empty means AI stays off.
variable "model_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "model_name" {
  type    = string
  default = "claude-sonnet-5"
}
