# This configuration simulates a scenario where some protected resources are being deleted
# This should trigger CRITICAL risks in the gatekeeper

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

# PROTECTED RESOURCES THAT WILL BE DELETED - SHOULD TRIGGER CRITICAL RISKS
resource "aws_kms_key" "production_key" {
  description = "Production KMS key for data encryption"
  is_enabled  = true
}

resource "aws_vpc" "production_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = {
    Name        = "production-vpc"
    Environment = "production"
  }
}

resource "aws_subnet" "production_subnet" {
  vpc_id     = aws_vpc.production_vpc.id
  cidr_block = "10.0.1.0/24"
  tags = {
    Name        = "production-subnet"
    Environment = "production"
  }
}

# SECURITY GROUP WITH UNRESTRICTED ACCESS - SHOULD TRIGGER SECURITY RISK
resource "aws_security_group" "unrestricted_sg" {
  name        = "unrestricted-security-group"
  description = "Security group with unrestricted access"
  vpc_id      = aws_vpc.production_vpc.id

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

# SAFE RESOURCES THAT SHOULD BE CREATED
resource "aws_s3_bucket" "safe_bucket" {
  bucket = "safe-tf-gatekeeper-bucket-12345"
}

resource "aws_db_instance" "safe_rds" {
  identifier           = "safe-rds-instance"
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  username             = "admin"
  password             = "securepassword123"
  parameter_group_name = "default.mysql8.0"
  skip_final_snapshot  = true
}