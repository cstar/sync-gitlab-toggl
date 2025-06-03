#!/bin/bash
"""
Deployment script for Toggl-GitLab Sync Lambda
"""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="prod"
ACCOUNT=""
REGION="us-east-1"
DRY_RUN="false"
SCHEDULE="cron(0 9 * * ? *)"  # Daily at 9 AM UTC

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Environment name (default: prod)"
    echo "  -a, --account ACCOUNT    AWS Account ID (required)"
    echo "  -r, --region REGION      AWS Region (default: us-east-1)"
    echo "  -d, --dry-run            Enable dry run mode (default: false)"
    echo "  -s, --schedule CRON      Cron schedule expression (default: daily 9 AM UTC)"
    echo "  --gitlab-url URL         GitLab URL (default: https://gitlab.enki.io)"
    echo "  --gitlab-project-id ID   GitLab Project ID (default: 1)"
    echo "  --toggl-workspace-id ID  Toggl Workspace ID"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --account 123456789012 --environment prod"
    echo "  $0 -a 123456789012 -e dev --dry-run"
    echo "  $0 -a 123456789012 --schedule 'cron(0 18 * * ? *)'"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -a|--account)
            ACCOUNT="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN="true"
            shift
            ;;
        -s|--schedule)
            SCHEDULE="$2"
            shift 2
            ;;
        --gitlab-url)
            GITLAB_URL="$2"
            shift 2
            ;;
        --gitlab-project-id)
            GITLAB_PROJECT_ID="$2"
            shift 2
            ;;
        --toggl-workspace-id)
            TOGGL_WORKSPACE_ID="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$ACCOUNT" ]]; then
    print_error "AWS Account ID is required. Use --account or -a"
    show_usage
    exit 1
fi

print_status "Starting deployment with the following configuration:"
echo "  Environment: $ENVIRONMENT"
echo "  Account: $ACCOUNT"
echo "  Region: $REGION"
echo "  Dry Run: $DRY_RUN"
echo "  Schedule: $SCHEDULE"
echo ""

# Check if CDK is installed
if ! command -v cdk &> /dev/null; then
    print_error "AWS CDK is not installed. Please install it first:"
    echo "  npm install -g aws-cdk"
    exit 1
fi

# Check if we're in the right directory
if [[ ! -f "app.py" ]]; then
    print_error "Please run this script from the cdk/ directory"
    exit 1
fi

# Install Python dependencies
print_status "Installing Python dependencies..."
if [[ ! -d "venv" ]]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt

# Build Lambda package
print_status "Building Lambda deployment package..."
cd ..
python build_lambda.py
cd cdk

# Bootstrap CDK if needed
print_status "Checking CDK bootstrap status..."
if ! cdk bootstrap aws://$ACCOUNT/$REGION 2>/dev/null; then
    print_warning "CDK bootstrap required. Bootstrapping..."
    cdk bootstrap aws://$ACCOUNT/$REGION
fi

# Build context parameters
CONTEXT_PARAMS=""
CONTEXT_PARAMS="$CONTEXT_PARAMS -c account=$ACCOUNT"
CONTEXT_PARAMS="$CONTEXT_PARAMS -c region=$REGION"
CONTEXT_PARAMS="$CONTEXT_PARAMS -c environment=$ENVIRONMENT"
CONTEXT_PARAMS="$CONTEXT_PARAMS -c dry_run=$DRY_RUN"
CONTEXT_PARAMS="$CONTEXT_PARAMS -c schedule='$SCHEDULE'"

if [[ -n "$GITLAB_URL" ]]; then
    CONTEXT_PARAMS="$CONTEXT_PARAMS -c gitlab_url=$GITLAB_URL"
fi

if [[ -n "$GITLAB_PROJECT_ID" ]]; then
    CONTEXT_PARAMS="$CONTEXT_PARAMS -c gitlab_project_id=$GITLAB_PROJECT_ID"
fi

if [[ -n "$TOGGL_WORKSPACE_ID" ]]; then
    CONTEXT_PARAMS="$CONTEXT_PARAMS -c toggl_workspace_id=$TOGGL_WORKSPACE_ID"
fi

# Deploy the stack
print_status "Deploying CDK stack..."
cdk deploy $CONTEXT_PARAMS --require-approval never

if [[ $? -eq 0 ]]; then
    print_success "Deployment completed successfully!"
    echo ""
    print_warning "IMPORTANT: Don't forget to update the secrets with your actual API tokens:"
    echo "1. Go to AWS Secrets Manager in the console"
    echo "2. Find the secrets for environment '$ENVIRONMENT'"
    echo "3. Update the Toggl and GitLab API tokens"
    echo ""
    print_status "You can also use the AWS CLI:"
    echo "aws secretsmanager update-secret --secret-id toggl-gitlab-sync/$ENVIRONMENT/toggl-token --secret-string '{\"api_token\":\"YOUR_TOGGL_TOKEN\"}'"
    echo "aws secretsmanager update-secret --secret-id toggl-gitlab-sync/$ENVIRONMENT/gitlab-token --secret-string '{\"api_token\":\"YOUR_GITLAB_TOKEN\"}'"
else
    print_error "Deployment failed!"
    exit 1
fi 