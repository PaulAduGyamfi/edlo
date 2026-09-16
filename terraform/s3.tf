resource "aws_s3_bucket" "media" { bucket = "edlo-media-${var.environment}" }

resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true # ALL FOUR. Always.
}

resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    id     = "media"
    status = "Enabled"
    filter { prefix = "episodes/" }
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    noncurrent_version_expiration { noncurrent_days = 30 }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

# Required for browser uploads. This is BUCKET CORS -- unrelated to the
# FastAPI CORS middleware, and both are needed.
resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  cors_rule {
   allowed_origins = [
      "https://${aws_cloudfront_distribution.web.domain_name}",
      "http://localhost:5173",
    ]
    allowed_methods = ["POST", "PUT", "GET", "HEAD"]
    allowed_headers = ["*"]
    # Without ExposeHeaders the browser cannot READ the checksum, so the
    # `complete` call has nothing to send.
    expose_headers  = ["ETag", "x-amz-checksum-sha256"]
    max_age_seconds = 3000
  }
}

# TLS-only, as an explicit Deny that no Allow can override.
data "aws_iam_policy_document" "media_bucket" {
  statement {
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.media.arn, "${aws_s3_bucket.media.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "media" {
  bucket = aws_s3_bucket.media.id
  policy = data.aws_iam_policy_document.media_bucket.json
}

# The API task role gains its FIRST permission. It was created empty in Ch 7.
resource "aws_iam_role_policy" "api_s3" {
  role = aws_iam_role.api_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ObjectsUnderEpisodesPrefixOnly"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject",
        "s3:GetObjectAttributes"]
        Resource = "${aws_s3_bucket.media.arn}/episodes/*"
      },
      {
        # ListBucket is a BUCKET-level action, so it needs the bucket ARN,
        # while GetObject is object-level and needs bucket/*. Different ARNs
        # in the same policy -- the thing everyone gets wrong first time.
        Sid       = "ListOnlyThatPrefix"
        Effect    = "Allow"
        Action    = "s3:ListBucket"
        Resource  = aws_s3_bucket.media.arn
        Condition = { StringLike = { "s3:prefix" = ["episodes/*"] } }
      },
    ]
  })
}
