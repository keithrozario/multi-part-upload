resource "aws_s3_bucket" "b" {
  bucket_prefix = "multipart-test"
  acl           = "private"
  force_destroy = true
  
  versioning {
    enabled = true
  }
  
  lifecycle_rule {
    id                                     = "delete-old-parts"
    enabled                                = true
    abort_incomplete_multipart_upload_days = 1
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        # We will use the default KMS key (aws/s3)
        sse_algorithm     = "aws:kms"
      }
    }
  }

}

resource "aws_ssm_parameter" "bucket_name" {
  name  = "${var.ssm_prefix}/${var.bucket_logical_name}/name"
  type  = "String"
  value = aws_s3_bucket.b.id
}

resource "aws_ssm_parameter" "bucket_arn" {
  name  = "${var.ssm_prefix}/${var.bucket_logical_name}/arn"
  type  = "String"
  value = aws_s3_bucket.b.arn
}