#!/usr/bin/env python3
"""CDK App for Toggl-GitLab Sync Lambda"""

import aws_cdk as cdk
from sync_stack import TogglGitLabSyncStack

app = cdk.App()

# Get environment configuration
account = app.node.try_get_context("account") or "123456789012"
region = app.node.try_get_context("region") or "us-east-1"
env_name = app.node.try_get_context("environment") or "prod"

# Create the stack
stack = TogglGitLabSyncStack(
    app, 
    f"TogglGitLabSync-{env_name}",
    env=cdk.Environment(account=account, region=region),
    env_name=env_name,
    description="Daily sync between Toggl Track and GitLab time tracking"
)

# Add tags
cdk.Tags.of(app).add("Project", "TogglGitLabSync")
cdk.Tags.of(app).add("Environment", env_name)
cdk.Tags.of(app).add("ManagedBy", "CDK")

app.synth() 