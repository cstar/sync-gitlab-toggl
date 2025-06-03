#!/usr/bin/env python3
"""AWS Lambda handler for Toggl-GitLab sync"""

import json
import logging
import os
from datetime import datetime, timezone
from sync_service import SyncService

# Use Lambda-specific config for AWS environment
try:
    from config_lambda import Config
except ImportError:
    # Fallback to regular config for local testing
    from config import Config

# Configure logging for CloudWatch
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    AWS Lambda handler function
    
    Args:
        event: Lambda event data (from EventBridge scheduler)
        context: Lambda context object
    
    Returns:
        dict: Response with status and summary
    """
    try:
        logger.info("Starting Toggl-GitLab sync Lambda execution")
        logger.info(f"Event: {json.dumps(event)}")
        
        # Override config for Lambda environment
        if hasattr(Config, 'DRY_RUN'):
            Config.DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'
        if hasattr(Config, 'SYNC_DAYS_BACK'):
            Config.SYNC_DAYS_BACK = int(os.getenv('DAYS_BACK', '1'))
        
        logger.info(f"Configuration: DRY_RUN={getattr(Config, 'DRY_RUN', 'unknown')}, DAYS_BACK={getattr(Config, 'SYNC_DAYS_BACK', 'unknown')}")
        
        # Initialize sync service
        sync_service = SyncService()
        
        # Test connections first
        if not sync_service.test_connections():
            raise Exception("Connection tests failed")
        
        # Perform sync (no parameters needed)
        logger.info("Starting sync process...")
        results = sync_service.sync_time_entries()
        
        # Prepare response
        response = {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'results': {
                    'processed_entries': results.get('processed_entries', 0),
                    'synced_entries': results.get('synced_entries', 0),
                    'created_issues': results.get('created_issues', 0),
                    'skipped_entries': results.get('skipped_entries', 0),
                    'errors': results.get('errors', 0),
                    'total_time_synced': results.get('total_time_synced', 0),
                    'billable_time_synced': results.get('billable_time_synced', 0)
                },
                'dry_run': getattr(Config, 'DRY_RUN', True)
            })
        }
        
        logger.info(f"Sync completed successfully: {results}")
        return response
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}", exc_info=True)
        
        # Return error response
        response = {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e),
                'dry_run': getattr(Config, 'DRY_RUN', True)
            })
        }
        
        return response

def test_handler(event=None, context=None):
    """Test handler for local testing"""
    test_event = event or {
        'source': 'aws.events',
        'detail-type': 'Scheduled Event',
        'detail': {}
    }
    
    # Mock context for testing
    class MockContext:
        def __init__(self):
            self.function_name = 'toggl-gitlab-sync'
            self.function_version = '$LATEST'
            self.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:toggl-gitlab-sync'
            self.memory_limit_in_mb = 512
            self.remaining_time_in_millis = 30000
            self.log_group_name = '/aws/lambda/toggl-gitlab-sync'
            self.log_stream_name = '2025/06/03/[$LATEST]test'
            self.aws_request_id = 'test-request-id'
    
    mock_context = context or MockContext()
    
    return lambda_handler(test_event, mock_context)

if __name__ == "__main__":
    # For local testing
    print("Testing Lambda handler locally...")
    result = test_handler()
    print(f"Result: {json.dumps(result, indent=2)}") 