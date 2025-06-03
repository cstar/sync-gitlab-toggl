# Toggl-GitLab Sync Lambda Deployment

This directory contains AWS CDK infrastructure code to deploy the Toggl-GitLab sync tool as a Lambda function that runs on a daily schedule.

## 🏗️ Architecture

The CDK stack creates:

- **Lambda Function**: Runs the sync logic with 5-minute timeout and 512MB memory
- **EventBridge Rule**: Triggers the Lambda daily (configurable schedule)
- **Secrets Manager**: Stores Toggl and GitLab API tokens securely
- **IAM Roles**: Minimal permissions for Lambda execution and secret access
- **CloudWatch Logs**: Centralized logging with 1-month retention

## 📋 Prerequisites

1. **AWS CLI** configured with appropriate permissions
2. **AWS CDK** v2.100+ installed globally: `npm install -g aws-cdk@latest`
3. **Python 3.11+** for the Lambda runtime
4. **Toggl Track API token** from your Toggl profile
5. **GitLab API token** with appropriate project permissions

## 🚀 Quick Start

### 1. Deploy the Infrastructure

```bash
cd cdk/
./deploy.sh --account YOUR_AWS_ACCOUNT_ID --environment prod
```

The deployment script will automatically:
- Build the Lambda package from source files
- Install CDK dependencies
- Deploy the complete infrastructure

### 2. Update API Tokens

After deployment, update the secrets with your actual API tokens:

```bash
# Update Toggl token
aws secretsmanager update-secret \
  --secret-id toggl-gitlab-sync/prod/toggl-token \
  --secret-string '{"api_token":"YOUR_TOGGL_TOKEN"}'

# Update GitLab token  
aws secretsmanager update-secret \
  --secret-id toggl-gitlab-sync/prod/gitlab-token \
  --secret-string '{"api_token":"YOUR_GITLAB_TOKEN"}'
```

### 3. Test the Function

```bash
# Invoke the Lambda function manually
aws lambda invoke \
  --function-name toggl-gitlab-sync-prod \
  --payload '{}' \
  response.json && cat response.json
```

## 🔧 Build Process

The deployment uses a clean build process to avoid file duplication:

1. **`../build_lambda.py`** - Copies only necessary files to `../src/`
2. **CDK** - Uses the clean `../src/` directory for Lambda deployment
3. **No Duplication** - Source files remain in the root directory

### Manual Build

If you need to rebuild the Lambda package manually:

```bash
cd .. # Go to project root
python build_lambda.py
cd cdk
```

## 🛠️ CDK Version Compatibility

If you see a CDK version mismatch error:

```
Cloud assembly schema version mismatch: Maximum schema version supported is 43.x.x, but found 44.0.0
```

**Solution**: Update your CDK CLI to the latest version:

```bash
# Update CDK CLI globally
npm install -g aws-cdk@latest

# Verify version
cdk --version
```

## ⚙️ Configuration Options

### Deployment Script Options

```bash
./deploy.sh [OPTIONS]

Options:
  -e, --environment ENV    Environment name (default: prod)
  -a, --account ACCOUNT    AWS Account ID (required)
  -r, --region REGION      AWS Region (default: us-east-1)
  -d, --dry-run            Enable dry run mode (default: false)
  -s, --schedule CRON      Cron schedule expression (default: daily 9 AM UTC)
  --gitlab-url URL         GitLab URL (default: https://gitlab.enki.io)
  --gitlab-project-id ID   GitLab Project ID (default: 1)
  --toggl-workspace-id ID  Toggl Workspace ID
  -h, --help               Show help message
```

### Environment Variables

The Lambda function supports these environment variables (set via CDK context):

| Variable | Default | Description |
|----------|---------|-------------|
| `DRY_RUN` | `false` | Run in dry-run mode (no actual changes) |
| `DAYS_BACK` | `1` | Number of days to sync backwards |
| `AUTO_CREATE_ISSUES` | `false` | Create new GitLab issues for unmatched entries |
| `PREVENT_DUPLICATES` | `true` | Prevent duplicate time entries |
| `MINIMUM_DURATION` | `300` | Minimum duration in seconds (5 minutes) |
| `ROUND_TIME_TO_MINUTES` | `15` | Round time to nearest X minutes |
| `ONLY_BILLABLE` | `false` | Only sync billable time entries |
| `EXCLUDE_WEEKENDS` | `false` | Skip weekend entries |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## 📅 Schedule Configuration

The default schedule runs daily at 9 AM UTC. You can customize this:

```bash
# Run every weekday at 6 PM UTC
./deploy.sh -a 123456789012 --schedule "cron(0 18 ? * MON-FRI *)"

# Run twice daily at 9 AM and 6 PM UTC
./deploy.sh -a 123456789012 --schedule "cron(0 9,18 * * ? *)"

# Run every hour during business hours (9 AM - 6 PM UTC, Mon-Fri)
./deploy.sh -a 123456789012 --schedule "cron(0 9-18 ? * MON-FRI *)"
```

## 🌍 Multi-Environment Deployment

Deploy to different environments:

```bash
# Production environment
./deploy.sh -a 123456789012 -e prod

# Development environment with dry-run enabled
./deploy.sh -a 123456789012 -e dev --dry-run

# Staging environment with different schedule
./deploy.sh -a 123456789012 -e staging --schedule "cron(0 12 * * ? *)"
```

## 📊 Monitoring & Logs

### CloudWatch Logs

View logs in the AWS Console or via CLI:

```bash
# View recent logs
aws logs tail /aws/lambda/toggl-gitlab-sync-prod --follow

# View logs for specific time range
aws logs filter-log-events \
  --log-group-name /aws/lambda/toggl-gitlab-sync-prod \
  --start-time $(date -d '1 hour ago' +%s)000
```

### CloudWatch Metrics

Monitor Lambda execution metrics:
- **Duration**: Execution time
- **Errors**: Failed executions
- **Invocations**: Total executions
- **Throttles**: Rate limiting events

### Custom Metrics

The Lambda function logs structured data that can be used for custom metrics:
- Number of entries processed
- Number of entries synced
- Total time synced
- Errors encountered

## 🔧 Troubleshooting

### Common Issues

1. **CDK Version Mismatch**: Update CDK CLI: `npm install -g aws-cdk@latest`
2. **Permission Denied**: Ensure your AWS credentials have sufficient permissions
3. **Secret Not Found**: Make sure you've updated the secrets after deployment
4. **Lambda Timeout**: Increase timeout if processing large amounts of data
5. **API Rate Limits**: Adjust schedule frequency if hitting rate limits

### Debug Mode

Enable debug logging by updating the environment variable:

```bash
aws lambda update-function-configuration \
  --function-name toggl-gitlab-sync-prod \
  --environment Variables='{LOG_LEVEL=DEBUG}'
```

### Manual Testing

Test the Lambda function locally:

```bash
cd ..  # Go back to project root
python lambda_handler.py
```

## 🔄 Updates & Maintenance

### Update the Function Code

After making changes to the sync logic:

```bash
./deploy.sh -a YOUR_ACCOUNT_ID -e prod
```

The deployment will automatically rebuild the Lambda package.

### Update Configuration

Modify environment variables without redeploying:

```bash
aws lambda update-function-configuration \
  --function-name toggl-gitlab-sync-prod \
  --environment Variables='{DRY_RUN=false,DAYS_BACK=2}'
```

### Rotate API Tokens

Update secrets when tokens change:

```bash
aws secretsmanager update-secret \
  --secret-id toggl-gitlab-sync/prod/toggl-token \
  --secret-string '{"api_token":"NEW_TOKEN"}'
```

## 🗑️ Cleanup

To remove all resources:

```bash
cdk destroy TogglGitLabSync-prod
```

## 💰 Cost Estimation

Estimated monthly costs for typical usage:
- **Lambda**: ~$0.20 (daily executions, 30-second average runtime)
- **Secrets Manager**: ~$0.80 (2 secrets)
- **CloudWatch Logs**: ~$0.50 (1GB logs/month)
- **EventBridge**: ~$0.00 (minimal usage)

**Total**: ~$1.50/month

## 🔐 Security

- API tokens stored in AWS Secrets Manager (encrypted at rest)
- Lambda execution role follows least-privilege principle
- No hardcoded credentials in code or configuration
- CloudWatch logs don't contain sensitive information

## 📞 Support

For issues or questions:
1. Check CloudWatch logs for error details
2. Review the main project README for sync logic issues
3. Verify API token permissions and validity
4. Check AWS service limits and quotas 