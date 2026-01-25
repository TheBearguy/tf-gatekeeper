#!/bin/bash

# Terraform Gatekeeper - JSON Extraction Script
# This script automates the process of extracting Terraform plan data to JSON format

set -e

echo "🔍 Starting Terraform Gatekeeper JSON extraction..."

# Check if terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "❌ Error: Terraform is not installed"
    exit 1
fi

# Initialize Terraform
echo "📦 Initializing Terraform..."
terraform init

# Create terraform plan
echo "📋 Creating Terraform plan..."
terraform plan -out=tfplan

# Convert plan to JSON format
echo "📄 Converting plan to JSON..."
terraform show -json tfplan > plan.json

# Clean up
rm -f tfplan

echo "✅ JSON extraction completed successfully!"
echo "📁 Generated: plan.json"
echo "🚀 Ready for gatekeeper analysis: python gatekeeper.py --plan plan.json"