provider "aws" {
  region = var.aws_region
}

module "test_bucket_1" {
  source              = "./s3_bucket_module"
  bucket_logical_name = var.bucket_logical_name
  ssm_prefix = var.ssm_prefix  
}