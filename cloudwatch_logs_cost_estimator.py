#!/usr/bin/env python3
# cloudwatch_logs_cost_estimator.py

# CloudWatchCashBack
# Calculate how much you'll save with AWS Lambda's new CloudWatch Logs tiered pricing. 
# This tool analyzes your current Lambda logs usage and compares costs between the 
#  old flat-rate model and the new tiered pricing structure introduced on May 1, 2025.

# ## Features
# - Fetches CloudWatch Logs usage data from your AWS account
# - Calculates costs using both old and new pricing models 
# - Provides detailed breakdowns by log storage class (Standard/Infrequent Access)
# - Generates comprehensive daily and monthly cost comparisons
# - Supports all AWS regions with region-specific pricing

# This should help you understand your CloudWatch logging costs and potential savings from the new tiered pricing model.
    

import boto3
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

def get_region():
    region_cli = ""
    for i, arg in enumerate(sys.argv):
        if arg == '--region' and i + 1 < len(sys.argv):
            region_cli = sys.argv[i + 1]
            break
    return region_cli


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Get region from CLI
region_cli = get_region()

def load_pricing_data():
    """
    Load CloudWatch pricing data from the JSON file.
    
    Returns:
        dict: Dictionary containing pricing data for all regions
    """
    try:
        pricing_file = Path(__file__).parent / 'cloudwatch_pricing.json'
        with open(pricing_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading pricing data: {str(e)}")
        raise

def calculate_old_cloudwatch_cost(standard_gb, ia_gb, region='us-east-1'):
    """
    Calculate CloudWatch Logs cost using the old pricing model based on region-specific pricing.
    
    Args:
        standard_gb (float): GB of logs ingested in standard storage
        ia_gb (float): GB of logs ingested in infrequent access storage
        region (str): AWS region to use for pricing
        
    Returns:
        float: Total cost in dollars
    """
    pricing_data = load_pricing_data()
    region_pricing = pricing_data.get(region, pricing_data['us-east-1'])  # Default to us-east-1 if region not found
    
    standard_cost = standard_gb * region_pricing['logs']['standard_ingestion']
    ia_cost = ia_gb * region_pricing['logs']['infrequent_ingestion']
    return standard_cost + ia_cost

def calculate_new_cloudwatch_cost(daily_gb_ingested, region='us-east-1', is_ia=False):
    """
    Calculate the cost of CloudWatch Logs based on tiered pricing for the specified region.
    
    Args:
        daily_gb_ingested (float): Daily GB ingested
        region (str): AWS region to use for pricing
        is_ia (bool): Whether this is for Infrequent Access logs
        
    Returns:
        dict: Dictionary containing cost details
    """
    pricing_data = load_pricing_data()
    region_pricing = pricing_data.get(region, pricing_data['us-east-1'])  # Default to us-east-1 if region not found
    
    # Get pricing tiers from the region's vended logs pricing
    pricing_key = 'to_cloudwatch_logs_infrequent' if is_ia else 'to_cloudwatch_logs_standard'
    vended_logs_pricing = region_pricing['logs']['vended_logs'][pricing_key]
    
    # Convert TB to GB
    TB_to_GB = 1000
    
    # Define tier thresholds in GB
    tier1_threshold = 10 * TB_to_GB  # 10 TB in GB
    tier2_threshold = 30 * TB_to_GB  # 30 TB in GB (10 + 20)
    tier3_threshold = 50 * TB_to_GB  # 50 TB in GB (10 + 20 + 20)
    
    # Get tier prices from the pricing data
    tier1_price = vended_logs_pricing['first_10tb']
    tier2_price = vended_logs_pricing['next_20tb']
    tier3_price = vended_logs_pricing['next_20tb_plus']
    tier4_price = vended_logs_pricing['over_50tb']
    
    # Calculate monthly GB (assuming 30 days)
    monthly_gb = daily_gb_ingested * 30
    
    # Initialize costs for each tier
    tier1_cost = 0
    tier2_cost = 0
    tier3_cost = 0
    tier4_cost = 0
    
    # Calculate Tier 1 cost (0-10 TB)
    tier1_usage = min(monthly_gb, tier1_threshold)
    tier1_cost = tier1_usage * tier1_price
    
    # Calculate Tier 2 cost (10-30 TB)
    if monthly_gb > tier1_threshold:
        tier2_usage = min(monthly_gb - tier1_threshold, tier2_threshold - tier1_threshold)
        tier2_cost = tier2_usage * tier2_price
    
    # Calculate Tier 3 cost (30-50 TB)
    if monthly_gb > tier2_threshold:
        tier3_usage = min(monthly_gb - tier2_threshold, tier3_threshold - tier2_threshold)
        tier3_cost = tier3_usage * tier3_price
    
    # Calculate Tier 4 cost (50+ TB)
    if monthly_gb > tier3_threshold:
        tier4_usage = monthly_gb - tier3_threshold
        tier4_cost = tier4_usage * tier4_price
    
    # Calculate total monthly and daily costs
    total_monthly_cost = tier1_cost + tier2_cost + tier3_cost + tier4_cost
    total_daily_cost = total_monthly_cost / 30
    
    return {
        "daily_gb_ingested": daily_gb_ingested,
        "monthly_gb_ingested": monthly_gb,
        "tier1_cost": tier1_cost,
        "tier2_cost": tier2_cost,
        "tier3_cost": tier3_cost,
        "tier4_cost": tier4_cost,
        "total_monthly_cost": total_monthly_cost,
        "total_daily_cost": total_daily_cost
    }

def get_lambda_log_usage_for_month():
    """
    Get the CloudWatch Logs usage for Lambda functions for the past month.
    
    Returns:
        dict: Dictionary containing daily usage data with standard and IA storage
    """
    logger.info("Starting to fetch Lambda log usage data for the past month")
    
    # Initialize CloudWatch Logs client
    logs_client = boto3.client('logs')
    cloudwatch_client = boto3.client('cloudwatch')
    
    # Get the current region
    if region_cli != "":
     region = region_cli
    else:
     region = logs_client.meta.region_name
    logger.info(f"Using region: {region}")
    
    # Get all log groups
    log_groups = []
    next_token = None
    
    logger.info("Fetching log groups from CloudWatch Logs")
    while True:
        if next_token:
            response = logs_client.describe_log_groups(nextToken=next_token)
        else:
            response = logs_client.describe_log_groups()
        
        # Filter for Lambda log groups
        for log_group in response.get('logGroups', []):
            if log_group['logGroupName'].startswith('/aws/lambda/'):
                log_groups.append({
                    'name': log_group['logGroupName'],
                    'class': log_group.get('logGroupClass', 'STANDARD')  # Default to STANDARD if not specified
                })
        
        logger.debug(f"Found {len(response.get('logGroups', []))} log groups in current batch")
        next_token = response.get('nextToken')
        if not next_token:
            break
    
    logger.info(f"Total Lambda log groups found: {len(log_groups)}")
    
    # Define the time period (last complete month)
    end_time = datetime.now()
    # Get the first day of the current month
    first_day_current_month = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Get the last day of the previous month
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    # For getting data, we need to go all the way to the first of the next month. 
    end_time = first_day_current_month
    # Get the first day of the previous month
    start_time = last_day_previous_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    logger.info(f"Analyzing data for the complete previous month: {start_time.strftime('%Y-%m-%d')} to {last_day_previous_month.strftime('%Y-%m-%d')}")
    
    # Get metrics for each Lambda log group
    daily_usage = {}
    
    for log_group in log_groups:
        logger.info(f"Fetching metrics for log group: {log_group['name']} that is type {log_group['class']}")
        try:
            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Logs',
                MetricName='IncomingBytes',
                Dimensions=[
                    {
                        'Name': 'LogGroupName',
                        'Value': log_group['name']
                    },
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # Daily metrics (24 hours in seconds)
                Statistics=['Sum']
            )
            
            # Convert bytes to GB and add to results
            for datapoint in response['Datapoints']:
                date = datapoint['Timestamp'].strftime('%Y-%m-%d')
                bytes_ingested = datapoint['Sum']
                gb_ingested = bytes_ingested / (1024 * 1024 * 1024)  # Convert bytes to GB
                
                if date not in daily_usage:
                    daily_usage[date] = {'standard': 0, 'ia': 0}
                
                if log_group['class'] == 'INFREQUENT_ACCESS':
                    daily_usage[date]['ia'] += gb_ingested
                else:  # STANDARD or DELIVERY
                    daily_usage[date]['standard'] += gb_ingested
                
        except Exception as e:
            logger.error(f"Error fetching metrics for {log_group['name']}: {str(e)}")
    
    logger.info(f"Successfully processed {len(daily_usage)} days of data")
    return daily_usage

def analyze_costs(daily_usage, region='us-east-1'):
    """
    Analyze the costs using both old and new pricing models.
    
    Args:
        daily_usage (dict): Dictionary containing daily usage data
        region (str): AWS region to use for pricing
        
    Returns:
        dict: Dictionary containing cost analysis results
    """
    total_standard_gb = sum(day['standard'] for day in daily_usage.values())
    total_ia_gb = sum(day['ia'] for day in daily_usage.values())
    total_gb = total_standard_gb + total_ia_gb
    
    # Calculate old pricing costs
    old_cost = calculate_old_cloudwatch_cost(total_standard_gb, total_ia_gb, region)
    
    # Calculate new pricing costs - handle standard and IA separately
    standard_cost_data = calculate_new_cloudwatch_cost(total_standard_gb / 30, region, is_ia=False)
    ia_cost_data = calculate_new_cloudwatch_cost(total_ia_gb / 30, region, is_ia=True)
    new_cost = standard_cost_data['total_monthly_cost'] + ia_cost_data['total_monthly_cost']
    
    # Calculate daily comparisons
    daily_comparisons = []
    for date, data in sorted(daily_usage.items()):
        daily_standard_gb = data['standard']
        daily_ia_gb = data['ia']
        daily_old_cost = calculate_old_cloudwatch_cost(daily_standard_gb, daily_ia_gb, region)
        
        # Calculate new costs separately for standard and IA
        daily_standard_cost = calculate_new_cloudwatch_cost(daily_standard_gb, region, is_ia=False)['total_daily_cost']
        daily_ia_cost = calculate_new_cloudwatch_cost(daily_ia_gb, region, is_ia=True)['total_daily_cost']
        daily_new_cost = daily_standard_cost + daily_ia_cost
        
        daily_comparisons.append({
            'date': date,
            'old_cost': daily_old_cost,
            'new_cost': daily_new_cost,
            'standard_gb': daily_standard_gb,
            'ia_gb': daily_ia_gb,
            'total_gb': daily_standard_gb + daily_ia_gb,
            'difference': daily_new_cost - daily_old_cost
        })
    
    return {
        'total_old_cost': old_cost,
        'total_new_cost': new_cost,
        'total_standard_gb': total_standard_gb,
        'total_ia_gb': total_ia_gb,
        'total_gb': total_gb,
        'daily_comparisons': daily_comparisons,
        'region': region
    }

def format_cost_report(analysis):
    """
    Format the cost analysis into a readable report.
    
    Args:
        analysis (dict): Cost analysis results from analyze_costs
        
    Returns:
        str: Formatted report
    """
    report = [
        "CloudWatch Logs Cost Analysis",
        "===========================",
        f"Region: {analysis['region']}",
        f"Total GB Ingested: {analysis['total_gb']:,.2f} GB",
        f"  - Standard Storage: {analysis['total_standard_gb']:,.2f} GB",
        f"  - Infrequent Access: {analysis['total_ia_gb']:,.2f} GB",
        "",
        f"Old Pricing Total Cost: ${analysis['total_old_cost']:,.2f}",
        f"New Pricing Total Cost: ${analysis['total_new_cost']:,.2f}",
        f"Cost Difference: ${analysis['total_new_cost'] - analysis['total_old_cost']:,.2f}",
    ]
    
    # Add percentage change
    if analysis['total_old_cost'] > 0:
        pct_change = ((analysis['total_new_cost'] - analysis['total_old_cost']) / 
                      analysis['total_old_cost'] * 100)
        report.append(f"Percentage Change: {pct_change:,.2f}%")
    
    report.extend([
        "\nDaily Breakdown:",
        "---------------"
    ])
    
    for day in analysis['daily_comparisons']:
        report.append(
            f"{day['date']}: "
            f"Old: ${day['old_cost']:,.2f}, "
            f"New: ${day['new_cost']:,.2f}, "
            f"Diff: ${day['difference']:,.2f}, "
            f"Usage: {day['total_gb']:,.2f} GB "
            f"(Standard: {day['standard_gb']:,.2f} GB, "
            f"IA: {day['ia_gb']:,.2f} GB)"
        )
    
    return "\n".join(report)

def main():
    """
    Main function to run the cost analysis.
    """

    logger.info("Starting CloudWatch Logs cost analysis")
   
    # Get the region from the CloudWatch client
# Check if region_cli exists and has a value, then set region
    if region_cli != "":
     region = region_cli
    else:
     region = boto3.client('logs').meta.region_name
    account_id = boto3.client('sts').get_caller_identity().get('Account')
    account_name = boto3.client('sts').get_caller_identity().get('Account')

    logger.info(f"Account ID: {account_id}")

    # Get usage data
    daily_usage = get_lambda_log_usage_for_month()

    # Analyze costs
    analysis = analyze_costs(daily_usage, region)
    
    # Generate report
    report = format_cost_report(analysis)
    
    # Create reports directory if it doesn't exist
    reports_dir = Path('reports')
    reports_dir.mkdir(exist_ok=True)
    
    # Write report to file with current date
    current_date = datetime.now().strftime('%Y%m%d')
    report_filename = reports_dir / f"{current_date}_CWLogsReport_{account_id}.md"
    
    try:
        with open(report_filename, 'w') as f:
            f.write(report)
        logger.info(f"Report written to {report_filename}")
    except Exception as e:
        logger.error(f"Error writing report to file: {str(e)}")
    
    # Print report to console
    print(report)
    
    return analysis

if __name__ == "__main__":
    main() 
