"""CDK Stack for Toggl-GitLab Sync Lambda Function"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
    aws_secretsmanager as secrets,
    aws_iam as iam,
)
from constructs import Construct
import os


class TogglGitLabSyncStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.env_name = env_name
        
        # Create secrets for sensitive configuration
        self._create_secrets()
        
        # Create the Lambda function
        self._create_lambda_function()
        
        # Create the scheduled trigger
        self._create_schedule()
        
        # Create CloudWatch dashboard (optional)
        self._create_monitoring()
    
    def _create_secrets(self):
        """Create AWS Secrets Manager secrets for sensitive data"""
        
        # Toggl API token secret
        self.toggl_secret = secrets.Secret(
            self, 
            "TogglApiSecret",
            secret_name=f"toggl-gitlab-sync/{self.env_name}/toggl-token",
            description="Toggl Track API token for sync service",
            generate_secret_string=secrets.SecretStringGenerator(
                secret_string_template='{"api_token": ""}',
                generate_string_key="api_token",
                exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\",
                include_space=False,
                require_each_included_type=False
            )
        )
        
        # GitLab API token secret
        self.gitlab_secret = secrets.Secret(
            self,
            "GitLabApiSecret", 
            secret_name=f"toggl-gitlab-sync/{self.env_name}/gitlab-token",
            description="GitLab API token for sync service",
            generate_secret_string=secrets.SecretStringGenerator(
                secret_string_template='{"api_token": ""}',
                generate_string_key="api_token",
                exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\",
                include_space=False,
                require_each_included_type=False
            )
        )
    
    def _create_lambda_function(self):
        """Create the Lambda function with all dependencies"""
        
        # Lambda execution role
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Grant permissions to read secrets
        self.toggl_secret.grant_read(lambda_role)
        self.gitlab_secret.grant_read(lambda_role)
        
        # Environment variables for Lambda
        environment_vars = {
            "TOGGL_SECRET_ARN": self.toggl_secret.secret_arn,
            "GITLAB_SECRET_ARN": self.gitlab_secret.secret_arn,
            "ENVIRONMENT": self.env_name,
            # Configuration from context or defaults
            "DRY_RUN": self.node.try_get_context("dry_run") or "false",
            "DAYS_BACK": str(self.node.try_get_context("days_back") or 1),
            "AUTO_CREATE_ISSUES": self.node.try_get_context("auto_create_issues") or "false",
            "PREVENT_DUPLICATES": self.node.try_get_context("prevent_duplicates") or "true",
            "MINIMUM_DURATION": str(self.node.try_get_context("minimum_duration") or 300),
            "ROUND_TIME_TO_MINUTES": str(self.node.try_get_context("round_time_to_minutes") or 15),
            "ONLY_BILLABLE": self.node.try_get_context("only_billable") or "false",
            "EXCLUDE_WEEKENDS": self.node.try_get_context("exclude_weekends") or "false",
            # GitLab configuration
            "GITLAB_URL": self.node.try_get_context("gitlab_url") or "https://gitlab.enki.io",
            "GITLAB_PROJECT_ID": str(self.node.try_get_context("gitlab_project_id") or 1),
            # Toggl configuration  
            "TOGGL_WORKSPACE_ID": str(self.node.try_get_context("toggl_workspace_id") or ""),
            "LOG_LEVEL": self.node.try_get_context("log_level") or "INFO",
        }
        
        # Create Lambda function
        self.lambda_function = _lambda.Function(
            self,
            "TogglGitLabSyncFunction",
            function_name=f"toggl-gitlab-sync-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset(
                path="../lambda_package",  # Point to the clean lambda package directory
            ),
            timeout=Duration.minutes(5),
            memory_size=512,
            environment=environment_vars,
            role=lambda_role,
            description=f"Daily sync between Toggl Track and GitLab ({self.env_name})",
            retry_attempts=1,
        )
        
        # Create log group with retention
        logs.LogGroup(
            self,
            "LambdaLogGroup",
            log_group_name=f"/aws/lambda/{self.lambda_function.function_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )
    
    def _create_schedule(self):
        """Create EventBridge rule to trigger Lambda daily"""
        
        # Get schedule from context or use default (daily at 9 AM UTC)
        schedule_expression = self.node.try_get_context("schedule") or "cron(0 9 * * ? *)"
        
        # Create EventBridge rule
        schedule_rule = events.Rule(
            self,
            "DailyTrigger",
            rule_name=f"toggl-gitlab-sync-{self.env_name}-trigger",
            description=f"Daily trigger for Toggl-GitLab sync ({self.env_name})",
            schedule=events.Schedule.expression(schedule_expression),
            enabled=True
        )
        
        # Add Lambda as target
        schedule_rule.add_target(
            targets.LambdaFunction(
                self.lambda_function,
                event=events.RuleTargetInput.from_object({
                    "source": "aws.events",
                    "detail-type": "Scheduled Event",
                    "detail": {
                        "environment": self.env_name,
                        "trigger": "daily-sync"
                    }
                })
            )
        )
        
        # Output the schedule
        cdk.CfnOutput(
            self,
            "ScheduleExpression",
            value=schedule_expression,
            description="Cron expression for the sync schedule"
        )
    
    def _create_monitoring(self):
        """Create CloudWatch monitoring resources"""
        
        # Output important ARNs and names
        cdk.CfnOutput(
            self,
            "LambdaFunctionName",
            value=self.lambda_function.function_name,
            description="Name of the Lambda function"
        )
        
        cdk.CfnOutput(
            self,
            "LambdaFunctionArn", 
            value=self.lambda_function.function_arn,
            description="ARN of the Lambda function"
        )
        
        cdk.CfnOutput(
            self,
            "TogglSecretArn",
            value=self.toggl_secret.secret_arn,
            description="ARN of the Toggl API token secret"
        )
        
        cdk.CfnOutput(
            self,
            "GitLabSecretArn",
            value=self.gitlab_secret.secret_arn,
            description="ARN of the GitLab API token secret"
        ) 