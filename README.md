# CloudWatch Cash Back

A tool to calculate potential savings from AWS Lambda's new CloudWatch Logs tiered pricing structure (effective May 1, 2025).

## Features

- Fetches CloudWatch Logs usage data from your AWS account
- Calculates costs using both old and new pricing models 
- Provides detailed breakdowns by log storage class (Standard/Infrequent Access)
- Generates comprehensive daily and monthly cost comparisons
- Supports all AWS regions with region-specific pricing

## Prerequisites

- Python 3.6 or higher
- AWS credentials configured (via AWS CLI or environment variables)
- Required AWS permissions to access CloudWatch Logs and CloudWatch metrics

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/CloudWatchCashBack.git
cd CloudWatchCashBack
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Pricing Data

The `cloudwatch_pricing.json` file contains the pricing data used for calculations:
- Current as of April 30, 2025 (the day before the new tiered pricing takes effect)
- Used to calculate cost comparisons between old and new pricing models

## Usage

Run the script with:
```bash
python cloudwatch_logs_cost_estimator.py
```

The script will:
1. Fetch your Lambda log usage data for the past month for the current AWS account configured
2. Calculate costs using both old and new pricing models
3. Generate a detailed report showing potential savings

## AWS Permissions Required

The following AWS permissions are required to run this tool:
- `logs:DescribeLogGroups` - To list and analyze Lambda log groups
- `cloudwatch:GetMetricStatistics` - To fetch log ingestion metrics
- `sts:GetCallerIdentity` - To identify the AWS account being analyzed

> **Note:** CloudWatch metrics are charged at $0.01 per 1,000 API requests. This tool makes one API request per log group to fetch metrics, so you may incur charges based on the number of Lambda log groups in your account.

## Output

The tool provides a detailed report including:
- Total GB ingested (Standard and Infrequent Access)
- Cost comparison between old and new pricing models
- Daily breakdown of usage and costs
- Percentage change in costs

## License

MIT License
