#!/usr/bin/env python3
"""
Toggl to GitLab Sync Tool

This script synchronizes time entries from Toggl Track to GitLab issues.
It can automatically create GitLab issues based on Toggl time entry descriptions
and log time spent on those issues.
"""

import click
import sys
import logging
from datetime import datetime, timedelta
from typing import Optional
from sync_service import SyncService
from config import Config
from toggl_client import TogglClient
from gitlab_client import GitLabClient


@click.group()
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']), 
              help='Override log level')
@click.option('--log-file', help='Override log file path')
def cli(log_level, log_file):
    """Toggl to GitLab synchronization tool with advanced features."""
    # Override logging config if provided
    if log_level:
        Config.LOG_LEVEL = log_level
    if log_file:
        Config.LOG_FILE = log_file
        Config.LOG_TO_FILE = True
    
    # Setup logging
    Config.setup_logging()


@cli.command()
@click.option('--dry-run', is_flag=True, help='Run in dry-run mode (no actual changes)')
@click.option('--days', default=None, type=int, help='Number of days back to sync (overrides config)')
@click.option('--project-id', help='Toggl project ID to filter by')
@click.option('--billable-only', is_flag=True, help='Sync only billable entries')
@click.option('--no-weekends', is_flag=True, help='Exclude weekend entries')
@click.option('--min-duration', type=int, help='Minimum duration in seconds')
@click.option('--round-to', type=click.Choice(['1', '5', '10', '15', '30']), help='Round time to minutes')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def sync(dry_run, days, project_id, billable_only, no_weekends, min_duration, round_to, verbose):
    """Sync time entries from Toggl to GitLab with advanced filtering."""
    try:
        # Override config if command line options provided
        if dry_run:
            Config.DRY_RUN = True
        if days:
            Config.SYNC_DAYS_BACK = days
        if project_id:
            Config.TOGGL_PROJECT_ID = project_id
        if billable_only:
            Config.SYNC_ONLY_BILLABLE = True
        if no_weekends:
            Config.EXCLUDE_WEEKENDS = True
        if min_duration:
            Config.MINIMUM_DURATION = min_duration
        if round_to:
            Config.ROUND_TIME_TO_MINUTES = int(round_to)
        if verbose:
            Config.LOG_LEVEL = 'DEBUG'
            Config.setup_logging()
        
        service = SyncService()
        
        # Test connections first
        if not service.test_connections():
            click.echo("❌ Connection test failed. Please check your API credentials.", err=True)
            sys.exit(1)
        
        # Show configuration summary
        if verbose:
            click.echo(Config.get_summary())
        
        # Perform sync
        stats = service.sync_time_entries()
        
        # Show detailed stats
        click.echo("\n📊 Sync Statistics:")
        click.echo(f"  • Processed entries: {stats['processed_entries']}")
        click.echo(f"  • Synced entries: {stats['synced_entries']}")
        click.echo(f"  • Created issues: {stats['created_issues']}")
        click.echo(f"  • Skipped entries: {stats['skipped_entries']}")
        click.echo(f"  • Errors: {stats['errors']}")
        
        # Exit with error code if there were errors
        if stats['errors'] > 0:
            sys.exit(1)
            
    except ValueError as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logging.exception("Unexpected error during sync")
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed connection info')
def test(verbose):
    """Test API connections to Toggl and GitLab."""
    try:
        if verbose:
            Config.LOG_LEVEL = 'DEBUG'
            Config.setup_logging()
        
        service = SyncService()
        
        click.echo("🔍 Testing API connections...")
        
        if service.test_connections():
            click.echo("✅ All API connections are working correctly!")
            
            if verbose:
                # Show detailed info
                click.echo("\n📋 Connection Details:")
                
                # Toggl info
                try:
                    user_info = service.toggl_client.get_user_info()
                    workspace_info = service.toggl_client.get_workspace_info()
                    projects = service.toggl_client.get_projects()
                    
                    click.echo(f"Toggl User: {user_info.get('fullname', 'Unknown')} ({user_info.get('email', 'N/A')})")
                    click.echo(f"Workspace: {workspace_info.get('name', 'Unknown')}")
                    click.echo(f"Available Projects: {len(projects)}")
                    
                except Exception as e:
                    click.echo(f"Error getting Toggl details: {e}")
                
                # GitLab info
                try:
                    project_info = service.gitlab_client.get_project_info()
                    milestones = service.gitlab_client.get_milestones()
                    labels = service.gitlab_client.get_labels()
                    
                    click.echo(f"GitLab Project: {project_info.get('path_with_namespace', 'Unknown')}")
                    click.echo(f"Project Visibility: {project_info.get('visibility', 'Unknown')}")
                    click.echo(f"Open Issues: {project_info.get('open_issues_count', 'N/A')}")
                    click.echo(f"Milestones: {len(milestones)}")
                    click.echo(f"Labels: {len(labels)}")
                    
                except Exception as e:
                    click.echo(f"Error getting GitLab details: {e}")
        else:
            click.echo("❌ API connection test failed.")
            sys.exit(1)
            
    except ValueError as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error testing connections: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Show full configuration details')
def config(verbose):
    """Show current configuration."""
    try:
        Config.validate()
        
        if verbose:
            click.echo(Config.get_summary())
        else:
            click.echo("Current Configuration:")
            click.echo("="*40)
            click.echo(f"Toggl Workspace ID: {Config.TOGGL_WORKSPACE_ID}")
            click.echo(f"Toggl Project ID: {Config.TOGGL_PROJECT_ID or 'All projects'}")
            click.echo(f"GitLab URL: {Config.GITLAB_URL}")
            click.echo(f"GitLab Project ID: {Config.GITLAB_PROJECT_ID}")
            click.echo(f"Sync Days Back: {Config.SYNC_DAYS_BACK}")
            click.echo(f"Dry Run Mode: {Config.DRY_RUN}")
            click.echo("="*40)
            
            # Show token status (but not the actual tokens)
            click.echo("API Token Status:")
            click.echo(f"  Toggl Token: {'✅ Set' if Config.TOGGL_API_TOKEN else '❌ Missing'}")
            click.echo(f"  GitLab Token: {'✅ Set' if Config.GITLAB_TOKEN else '❌ Missing'}")
        
    except ValueError as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('description')
@click.option('--all-patterns', is_flag=True, help='Test all patterns and show results')
def parse_ticket(description, all_patterns):
    """Test ticket parsing from a description string."""
    client = TogglClient("dummy", "dummy")  # We only need the parsing method
    result = client.extract_ticket_info(description)
    
    click.echo(f"Description: {description}")
    click.echo(f"Ticket ID: {result['ticket_id'] or 'None'}")
    click.echo(f"Ticket Name: {result['ticket_name']}")
    
    if all_patterns:
        click.echo("\n🔍 Testing all patterns:")
        patterns = [
            r'#(\d+):?\s*(.*)',  # #123: description
            r'([A-Z]+-\d+):?\s*(.*)',  # PROJ-123: description
            r'Issue\s+#(\d+):?\s*(.*)',  # Issue #123: description
            r'\[([A-Z]+-\d+)\]\s*(.*)',  # [PROJ-123] description
            r'\(([A-Z]+-\d+)\)\s*(.*)',  # (PROJ-123) description
            r'(\w+-\d+)\s*[-:]\s*(.*)',  # PROJ-123 - description
            r'([A-Z]{2,}-\d+)\b\s*(.*)',  # JIRA-123 description
            r'(\d+):\s*(.*)',  # 123: description
        ]
        
        pattern_names = [
            "Hash number (#123:)",
            "Project code (PROJ-123:)",
            "Issue prefix (Issue #123:)",
            "Square brackets ([PROJ-123])",
            "Parentheses ((PROJ-123))",
            "Dash/colon separator (PROJ-123 -)",
            "Word boundary (JIRA-123)",
            "Simple number (123:)"
        ]
        
        import re
        for i, (pattern, name) in enumerate(zip(patterns, pattern_names)):
            match = re.match(pattern, description.strip(), re.IGNORECASE)
            status = "✅ Match" if match else "❌ No match"
            if match:
                ticket_id = match.group(1)
                ticket_name = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else description
                click.echo(f"  {i+1}. {name}: {status} -> ID: {ticket_id}, Name: {ticket_name}")
            else:
                click.echo(f"  {i+1}. {name}: {status}")


@cli.command()
@click.option('--days', default=7, type=int, help='Number of days to analyze')
@click.option('--project-id', help='Toggl project ID to filter by')
@click.option('--format', type=click.Choice(['table', 'json']), default='table', help='Output format')
def analyze(days, project_id, format):
    """Analyze Toggl time entries without syncing."""
    try:
        # Override config for analysis
        Config.SYNC_DAYS_BACK = days
        if project_id:
            Config.TOGGL_PROJECT_ID = project_id
        
        # Create Toggl client
        toggl_client = TogglClient(
            Config.TOGGL_API_TOKEN,
            Config.TOGGL_WORKSPACE_ID,
            Config.TOGGL_USER_ID
        )
        
        # Get date range
        from datetime import datetime, timedelta
        import pytz
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=days)
        
        click.echo(f"📊 Analyzing Toggl entries from {start_date.date()} to {end_date.date()}")
        
        # Fetch and process entries
        entries = toggl_client.get_time_entries(
            start_date=start_date,
            end_date=end_date,
            project_id=project_id,
            only_billable=Config.SYNC_ONLY_BILLABLE,
            minimum_duration=Config.MINIMUM_DURATION
        )
        
        processed_entries = toggl_client.process_time_entries(
            entries,
            minimum_duration=Config.MINIMUM_DURATION,
            round_to_minutes=Config.ROUND_TIME_TO_MINUTES,
            exclude_weekends=Config.EXCLUDE_WEEKENDS
        )
        
        # Get detailed stats
        stats = toggl_client.get_detailed_stats(processed_entries)
        
        if format == 'json':
            import json
            click.echo(json.dumps(stats, indent=2, default=str))
        else:
            # Table format
            click.echo(f"\n📈 Analysis Results:")
            click.echo(f"  • Total entries: {stats.get('total_entries', 0)}")
            click.echo(f"  • Total time: {_format_duration(stats.get('total_duration', 0))}")
            click.echo(f"  • Billable time: {_format_duration(stats.get('billable_time', 0))}")
            click.echo(f"  • Non-billable time: {_format_duration(stats.get('non_billable_time', 0))}")
            click.echo(f"  • Entries with tickets: {stats.get('entries_with_tickets', 0)}")
            click.echo(f"  • Entries without tickets: {stats.get('entries_without_tickets', 0)}")
            click.echo(f"  • Average duration: {_format_duration(stats.get('average_duration', 0))}")
            
            if stats.get('time_saved_by_rounding', 0) != 0:
                click.echo(f"  • Time adjusted by rounding: {_format_duration(stats.get('time_saved_by_rounding', 0))}")
            
            # Project breakdown
            projects = stats.get('projects', {})
            if len(projects) > 1:
                click.echo(f"\n📁 Project Breakdown:")
                for proj_id, proj_stats in projects.items():
                    proj_name = f"Project {proj_id}" if proj_id != "No Project" else "No Project"
                    click.echo(f"  • {proj_name}: {proj_stats['count']} entries, {_format_duration(proj_stats['duration'])}")
        
    except Exception as e:
        click.echo(f"❌ Error analyzing entries: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('issue_id', type=int)
@click.option('--show-time-entries', is_flag=True, help='Show time tracking entries')
def issue_info(issue_id, show_time_entries):
    """Get detailed information about a GitLab issue."""
    try:
        gitlab_client = GitLabClient(
            Config.GITLAB_URL,
            Config.GITLAB_TOKEN,
            Config.GITLAB_PROJECT_ID
        )
        
        # Find issue
        issue = gitlab_client.find_issue_by_ticket_id(str(issue_id))
        if not issue:
            click.echo(f"❌ Issue #{issue_id} not found.")
            sys.exit(1)
        
        # Display issue info
        click.echo(f"📋 Issue #{issue['iid']}: {issue['title']}")
        click.echo(f"State: {issue['state']}")
        click.echo(f"URL: {issue['web_url']}")
        
        if issue['assignees']:
            click.echo(f"Assignees: {', '.join(issue['assignees'])}")
        
        if issue['labels']:
            click.echo(f"Labels: {', '.join(issue['labels'])}")
        
        if issue['milestone']:
            click.echo(f"Milestone: {issue['milestone']}")
        
        # Get time stats
        time_stats = gitlab_client.get_issue_time_stats(issue['iid'])
        if time_stats:
            click.echo(f"\n⏱️  Time Tracking:")
            if time_stats.get('human_time_estimate'):
                click.echo(f"  • Estimate: {time_stats['human_time_estimate']}")
            if time_stats.get('human_total_time_spent'):
                click.echo(f"  • Time spent: {time_stats['human_total_time_spent']}")
        
        # Show time entries if requested
        if show_time_entries:
            entries = gitlab_client.get_time_tracking_entries(issue['iid'])
            if entries:
                click.echo(f"\n📝 Time Entries ({len(entries)}):")
                for entry in entries:
                    click.echo(f"  • {entry['spent_at']}: {entry['duration']} - {entry['summary']}")
                    if entry['user']:
                        click.echo(f"    by {entry['user']}")
        
    except Exception as e:
        click.echo(f"❌ Error getting issue info: {e}", err=True)
        sys.exit(1)


def _format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format"""
    if seconds == 0:
        return "0m"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
    else:
        return f"{minutes}m"


if __name__ == '__main__':
    cli() 