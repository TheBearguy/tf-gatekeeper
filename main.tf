terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_s3_bucket" "test_bucket" {
  bucket = "tf-gatekeeper-test-bucket-12345"
}

# This resource will be deleted to test gatekeeper
resource "aws_s3_bucket_versioning" "test_bucket_versioning" {
  bucket = aws_s3_bucket.test_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket" "bucket_to_delete" {
  bucket = "bucket-to-be-deleted-12345"
}

resource "aws_db_instance" "test_rds" {
  identifier           = "tf-gatekeeper-rds"
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  username             = "admin"
  password             = "securepassword123"
  parameter_group_name = "default.mysql8.0"
  skip_final_snapshot  = true
}

resource "aws_security_group" "test_sg" {
  name        = "tf-gatekeeper-sg"
  description = "Test security group for terraform gatekeeper"
  vpc_id      = "vpc-12345678"

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

