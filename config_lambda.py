"""Configuration for Lambda deployment using AWS Secrets Manager"""

import os
import json
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class LambdaConfig:
    """Configuration class for Lambda environment using AWS Secrets Manager"""
    
    def __init__(self):
        self._secrets_client = None
        self._toggl_token = None
        self._gitlab_token = None
        self._load_config()
    
    @property
    def secrets_client(self):
        """Get boto3 secrets manager client"""
        if self._secrets_client is None:
            self._secrets_client = boto3.client('secretsmanager')
        return self._secrets_client
    
    def _get_secret(self, secret_arn):
        """Get secret value from AWS Secrets Manager"""
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            secret_data = json.loads(response['SecretString'])
            return secret_data.get('api_token', '')
        except ClientError as e:
            logger.error(f"Failed to get secret {secret_arn}: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse secret JSON {secret_arn}: {e}")
            raise
    
    def _load_config(self):
        """Load configuration from environment variables and secrets"""
        
        # Get secrets from Secrets Manager
        toggl_secret_arn = os.getenv('TOGGL_SECRET_ARN')
        gitlab_secret_arn = os.getenv('GITLAB_SECRET_ARN')
        
        if toggl_secret_arn:
            self._toggl_token = self._get_secret(toggl_secret_arn)
        else:
            # Fallback to environment variable for local testing
            self._toggl_token = os.getenv('TOGGL_TOKEN', '')
            
        if gitlab_secret_arn:
            self._gitlab_token = self._get_secret(gitlab_secret_arn)
        else:
            # Fallback to environment variable for local testing
            self._gitlab_token = os.getenv('GITLAB_TOKEN', '')
    
    # Toggl Configuration
    @property
    def TOGGL_TOKEN(self):
        return self._toggl_token
    
    @property
    def TOGGL_WORKSPACE_ID(self):
        return os.getenv('TOGGL_WORKSPACE_ID', '')
    
    @property
    def TOGGL_PROJECT_ID(self):
        return os.getenv('TOGGL_PROJECT_ID', '')
    
    @property
    def TOGGL_USER_ID(self):
        return os.getenv('TOGGL_USER_ID', '')
    
    # GitLab Configuration
    @property
    def GITLAB_TOKEN(self):
        return self._gitlab_token
    
    @property
    def GITLAB_URL(self):
        return os.getenv('GITLAB_URL', 'https://gitlab.enki.io')
    
    @property
    def GITLAB_PROJECT_ID(self):
        return os.getenv('GITLAB_PROJECT_ID', '1')
    
    @property
    def GITLAB_DEFAULT_ASSIGNEE(self):
        return os.getenv('GITLAB_DEFAULT_ASSIGNEE', '')
    
    @property
    def GITLAB_DEFAULT_MILESTONE(self):
        return os.getenv('GITLAB_DEFAULT_MILESTONE', '')
    
    # Sync Settings
    @property
    def DAYS_BACK(self):
        return int(os.getenv('DAYS_BACK', '1'))
    
    @property
    def DRY_RUN(self):
        return os.getenv('DRY_RUN', 'false').lower() == 'true'
    
    @property
    def AUTO_CREATE_ISSUES(self):
        return os.getenv('AUTO_CREATE_ISSUES', 'false').lower() == 'true'
    
    @property
    def MINIMUM_DURATION(self):
        return int(os.getenv('MINIMUM_DURATION', '300'))
    
    @property
    def ROUND_TIME_TO_MINUTES(self):
        return int(os.getenv('ROUND_TIME_TO_MINUTES', '1'))
    
    @property
    def ONLY_BILLABLE(self):
        return os.getenv('ONLY_BILLABLE', 'false').lower() == 'true'
    
    @property
    def EXCLUDE_WEEKENDS(self):
        return os.getenv('EXCLUDE_WEEKENDS', 'false').lower() == 'true'
    
    @property
    def PREVENT_DUPLICATES(self):
        return os.getenv('PREVENT_DUPLICATES', 'true').lower() == 'true'
    
    @property
    def TIME_ZONE(self):
        return os.getenv('TIME_ZONE', 'UTC')
    
    # Issue Creation Settings
    @property
    def MIN_DESCRIPTION_LENGTH(self):
        return int(os.getenv('MIN_DESCRIPTION_LENGTH', '5'))
    
    @property
    def SKIP_TERMS(self):
        terms = os.getenv('SKIP_TERMS', 'meeting,break,lunch,admin,misc,other,call')
        return [term.strip().lower() for term in terms.split(',')]
    
    @property
    def DEFAULT_LABELS(self):
        labels = os.getenv('DEFAULT_LABELS', 'toggl-sync')
        return [label.strip() for label in labels.split(',') if label.strip()]
    
    @property
    def ADD_TIME_ESTIMATES(self):
        return os.getenv('ADD_TIME_ESTIMATES', 'false').lower() == 'true'
    
    @property
    def ESTIMATE_MULTIPLIER(self):
        return float(os.getenv('ESTIMATE_MULTIPLIER', '1.5'))
    
    # Logging
    @property
    def LOG_LEVEL(self):
        return os.getenv('LOG_LEVEL', 'INFO')
    
    @property
    def LOG_TO_FILE(self):
        return os.getenv('LOG_TO_FILE', 'false').lower() == 'true'
    
    @property
    def LOG_FILE(self):
        return os.getenv('LOG_FILE', 'sync.log')
    
    # Environment
    @property
    def ENVIRONMENT(self):
        return os.getenv('ENVIRONMENT', 'prod')
    
    def validate(self):
        """Validate configuration"""
        errors = []
        
        if not self.TOGGL_TOKEN:
            errors.append("TOGGL_TOKEN is required")
        
        if not self.GITLAB_TOKEN:
            errors.append("GITLAB_TOKEN is required")
        
        if not self.GITLAB_URL:
            errors.append("GITLAB_URL is required")
        
        if not self.GITLAB_PROJECT_ID:
            errors.append("GITLAB_PROJECT_ID is required")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")
        
        return True

# Global config instance for Lambda
Config = LambdaConfig() 