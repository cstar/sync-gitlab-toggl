import os
import logging
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file
load_dotenv()

class Config:
    # Toggl API configuration
    TOGGL_API_TOKEN = os.getenv('TOGGL_API_TOKEN')
    TOGGL_WORKSPACE_ID = os.getenv('TOGGL_WORKSPACE_ID')
    TOGGL_PROJECT_ID = os.getenv('TOGGL_PROJECT_ID')  # Optional: filter by specific project
    TOGGL_USER_ID = os.getenv('TOGGL_USER_ID')  # Optional: filter by specific user
    
    # GitLab API configuration
    GITLAB_URL = os.getenv('GITLAB_URL', 'https://gitlab.com')
    GITLAB_TOKEN = os.getenv('GITLAB_TOKEN')
    GITLAB_PROJECT_ID = os.getenv('GITLAB_PROJECT_ID')
    GITLAB_DEFAULT_ASSIGNEE = os.getenv('GITLAB_DEFAULT_ASSIGNEE')  # Optional: default assignee for new issues
    GITLAB_DEFAULT_MILESTONE = os.getenv('GITLAB_DEFAULT_MILESTONE')  # Optional: default milestone
    
    # Sync configuration
    SYNC_DAYS_BACK = int(os.getenv('SYNC_DAYS_BACK', '7'))  # How many days back to sync
    DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'  # Test mode
    AUTO_CREATE_ISSUES = os.getenv('AUTO_CREATE_ISSUES', 'true').lower() == 'true'  # Auto-create issues
    MINIMUM_DURATION = int(os.getenv('MINIMUM_DURATION', '300'))  # Minimum duration in seconds (5 minutes)
    ROUND_TIME_TO_MINUTES = int(os.getenv('ROUND_TIME_TO_MINUTES', '15'))  # Round time to nearest X minutes
    
    # Issue creation rules
    MIN_DESCRIPTION_LENGTH = int(os.getenv('MIN_DESCRIPTION_LENGTH', '5'))
    SKIP_GENERIC_TERMS = os.getenv('SKIP_GENERIC_TERMS', 'meeting,break,lunch,admin,misc,other,call').split(',')
    ISSUE_LABELS = os.getenv('ISSUE_LABELS', 'toggl-sync').split(',') if os.getenv('ISSUE_LABELS') else ['toggl-sync']
    
    # Time tracking configuration
    ADD_TIME_ESTIMATES = os.getenv('ADD_TIME_ESTIMATES', 'false').lower() == 'true'
    ESTIMATE_MULTIPLIER = float(os.getenv('ESTIMATE_MULTIPLIER', '1.5'))  # Multiply logged time for estimates
    
    # Logging configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.getenv('LOG_FILE', 'sync.log')
    LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
    
    # Advanced features
    SYNC_ONLY_BILLABLE = os.getenv('SYNC_ONLY_BILLABLE', 'false').lower() == 'true'
    EXCLUDE_WEEKENDS = os.getenv('EXCLUDE_WEEKENDS', 'false').lower() == 'true'
    TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')
    PREVENT_DUPLICATES = os.getenv('PREVENT_DUPLICATES', 'true').lower() == 'true'  # Prevent duplicate time entries
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present"""
        required_fields = [
            'TOGGL_API_TOKEN',
            'TOGGL_WORKSPACE_ID', 
            'GITLAB_TOKEN',
            'GITLAB_PROJECT_ID'
        ]
        
        missing_fields = []
        invalid_fields = []
        
        for field in required_fields:
            value = getattr(cls, field)
            if not value:
                missing_fields.append(field)
            elif field == 'GITLAB_PROJECT_ID' and not value.isdigit():
                invalid_fields.append(f"{field} must be numeric")
        
        # Validate numeric fields
        if cls.SYNC_DAYS_BACK <= 0:
            invalid_fields.append("SYNC_DAYS_BACK must be greater than 0")
        
        if cls.MINIMUM_DURATION < 0:
            invalid_fields.append("MINIMUM_DURATION must be >= 0")
        
        if cls.ROUND_TIME_TO_MINUTES not in [1, 5, 10, 15, 30]:
            invalid_fields.append("ROUND_TIME_TO_MINUTES must be one of: 1, 5, 10, 15, 30")
        
        # Collect all errors
        errors = []
        if missing_fields:
            errors.append(f"Missing required configuration: {', '.join(missing_fields)}")
        if invalid_fields:
            errors.extend(invalid_fields)
        
        if errors:
            raise ValueError('\n'.join(errors))
        
        return True
    
    @classmethod
    def setup_logging(cls):
        """Setup logging configuration"""
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create logger
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, cls.LOG_LEVEL))
        
        # Clear existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler (if enabled)
        if cls.LOG_TO_FILE:
            file_handler = logging.FileHandler(cls.LOG_FILE)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    @classmethod
    def get_summary(cls) -> str:
        """Get a summary of current configuration"""
        return f"""
Configuration Summary:
=====================
Toggl:
  - Workspace ID: {cls.TOGGL_WORKSPACE_ID}
  - Project ID: {cls.TOGGL_PROJECT_ID or 'All projects'}
  - User ID: {cls.TOGGL_USER_ID or 'All users'}

GitLab:
  - URL: {cls.GITLAB_URL}
  - Project ID: {cls.GITLAB_PROJECT_ID}
  - Default Assignee: {cls.GITLAB_DEFAULT_ASSIGNEE or 'None'}
  - Default Milestone: {cls.GITLAB_DEFAULT_MILESTONE or 'None'}

Sync Settings:
  - Days back: {cls.SYNC_DAYS_BACK}
  - Dry run: {cls.DRY_RUN}
  - Auto-create issues: {cls.AUTO_CREATE_ISSUES}
  - Minimum duration: {cls.MINIMUM_DURATION}s
  - Round time to: {cls.ROUND_TIME_TO_MINUTES} minutes
  - Only billable: {cls.SYNC_ONLY_BILLABLE}
  - Exclude weekends: {cls.EXCLUDE_WEEKENDS}
  - Prevent duplicates: {cls.PREVENT_DUPLICATES}
  - Time zone: {cls.TIME_ZONE}

Issue Creation:
  - Min description length: {cls.MIN_DESCRIPTION_LENGTH}
  - Skip terms: {', '.join(cls.SKIP_GENERIC_TERMS)}
  - Default labels: {', '.join(cls.ISSUE_LABELS)}
  - Add time estimates: {cls.ADD_TIME_ESTIMATES}
  - Estimate multiplier: {cls.ESTIMATE_MULTIPLIER}

Logging:
  - Level: {cls.LOG_LEVEL}
  - Log to file: {cls.LOG_TO_FILE}
  - Log file: {cls.LOG_FILE}
""" 