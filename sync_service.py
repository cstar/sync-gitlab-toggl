from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pytz
import logging
from config import Config
from toggl_client import TogglClient
from gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self):
        Config.validate()
        
        self.toggl_client = TogglClient(
            api_token=Config.TOGGL_API_TOKEN,
            workspace_id=Config.TOGGL_WORKSPACE_ID,
            user_id=Config.TOGGL_USER_ID
        )
        
        self.gitlab_client = GitLabClient(
            gitlab_url=Config.GITLAB_URL,
            api_token=Config.GITLAB_TOKEN,
            project_id=Config.GITLAB_PROJECT_ID
        )
        
        self.dry_run = Config.DRY_RUN
        self.sync_days_back = Config.SYNC_DAYS_BACK
        
        # Statistics
        self.stats = {
            'processed_entries': 0,
            'synced_entries': 0,
            'created_issues': 0,
            'errors': 0,
            'skipped_entries': 0,
            'time_estimates_added': 0,
            'total_time_synced': 0,
            'billable_time_synced': 0
        }
        
        logger.info("SyncService initialized")
    
    def get_sync_date_range(self) -> Tuple[datetime, datetime]:
        """Get the date range for syncing based on configuration"""
        # Use end of current day to ensure we capture all entries from today
        now = datetime.now(pytz.UTC)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        start_date = end_date - timedelta(days=self.sync_days_back)
        # Start from beginning of the start day
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_date, end_date
    
    def sync_time_entries(self) -> Dict:
        """Main sync method that fetches Toggl data and pushes to GitLab"""
        logger.info("Starting Toggl to GitLab sync...")
        logger.info(f"Dry run mode: {self.dry_run}")
        
        # Get date range
        start_date, end_date = self.get_sync_date_range()
        logger.info(f"Syncing time entries from {start_date.date()} to {end_date.date()}")
        
        # Get GitLab project info
        project_info = self.gitlab_client.get_project_info()
        if project_info:
            logger.info(f"Target GitLab project: {project_info.get('path_with_namespace', 'Unknown')}")
        
        # Fetch time entries from Toggl
        logger.info("Fetching time entries from Toggl...")
        time_entries = self.toggl_client.get_time_entries(
            start_date=start_date,
            end_date=end_date,
            project_id=Config.TOGGL_PROJECT_ID,
            only_billable=Config.SYNC_ONLY_BILLABLE,
            minimum_duration=Config.MINIMUM_DURATION
        )
        
        if not time_entries:
            logger.info("No time entries found in the specified date range.")
            return self.stats
        
        # Process time entries
        processed_entries = self.toggl_client.process_time_entries(
            time_entries,
            minimum_duration=Config.MINIMUM_DURATION,
            round_to_minutes=Config.ROUND_TIME_TO_MINUTES,
            exclude_weekends=Config.EXCLUDE_WEEKENDS
        )
        logger.info(f"Found {len(processed_entries)} time entries to process")
        
        # Show detailed analysis
        detailed_stats = self.toggl_client.get_detailed_stats(processed_entries)
        logger.info(f"Total time to sync: {self._format_duration(detailed_stats.get('total_duration', 0))}")
        logger.info(f"Billable time: {self._format_duration(detailed_stats.get('billable_time', 0))}")
        logger.info(f"Entries with tickets: {detailed_stats.get('entries_with_tickets', 0)}")
        logger.info(f"Entries without tickets: {detailed_stats.get('entries_without_tickets', 0)}")
        
        # Group entries by ticket for better organization
        entries_by_ticket = self._group_entries_by_ticket(processed_entries)
        
        # Sync each group of entries
        for ticket_info, entries in entries_by_ticket.items():
            self._sync_ticket_entries(ticket_info, entries)
        
        # Update final stats
        self.stats['total_time_synced'] = sum(entry['duration'] for entry in processed_entries if self._should_sync_entry(entry))
        self.stats['billable_time_synced'] = sum(entry['duration'] for entry in processed_entries if entry.get('billable') and self._should_sync_entry(entry))
        
        # Print summary
        self._print_sync_summary()
        
        return self.stats
    
    def _should_sync_entry(self, entry: Dict) -> bool:
        """Determine if an entry should be synced based on configuration"""
        # Check minimum duration
        if entry['duration'] < Config.MINIMUM_DURATION:
            return False
        
        # Check billable filter
        if Config.SYNC_ONLY_BILLABLE and not entry.get('billable', False):
            return False
        
        return True
    
    def _group_entries_by_ticket(self, entries: List[Dict]) -> Dict[Tuple, List[Dict]]:
        """Group time entries by ticket ID and name"""
        grouped = {}
        
        for entry in entries:
            ticket_key = (entry.get('ticket_id'), entry.get('ticket_name'))
            if ticket_key not in grouped:
                grouped[ticket_key] = []
            grouped[ticket_key].append(entry)
        
        return grouped
    
    def _sync_ticket_entries(self, ticket_info: Tuple, entries: List[Dict]):
        """Sync a group of time entries for a specific ticket"""
        ticket_id, ticket_name = ticket_info
        total_duration = sum(entry['duration'] for entry in entries)
        
        logger.info(f"Processing ticket: {ticket_id or 'No ID'} - {ticket_name}")
        logger.debug(f"  Entries: {len(entries)}, Total time: {self._format_duration(total_duration)}")
        
        self.stats['processed_entries'] += len(entries)
        
        # Find or create GitLab issue
        gitlab_issue = None
        
        if ticket_id:
            # Try to find existing issue
            gitlab_issue = self.gitlab_client.find_issue_by_ticket_id(ticket_id)
            
            if gitlab_issue:
                logger.info(f"  Found existing GitLab issue #{gitlab_issue['iid']}: {gitlab_issue['title']}")
            else:
                logger.info(f"  Issue {ticket_id} not found in GitLab")
        
        # If no issue found and we have a ticket name, consider creating one
        if not gitlab_issue and ticket_name and ticket_name.strip():
            if self._should_create_issue(ticket_name):
                if Config.AUTO_CREATE_ISSUES:
                    if not self.dry_run:
                        # Calculate estimate if enabled
                        estimate_seconds = None
                        if Config.ADD_TIME_ESTIMATES:
                            estimate_seconds = int(total_duration * Config.ESTIMATE_MULTIPLIER)
                        
                        gitlab_issue = self.gitlab_client.create_issue(
                            title=ticket_name,
                            description=f"Auto-created from Toggl time tracking\n\nOriginal ticket ID: {ticket_id or 'N/A'}\nTotal logged time: {self._format_duration(total_duration)}",
                            labels=Config.ISSUE_LABELS,
                            assignee=Config.GITLAB_DEFAULT_ASSIGNEE,
                            milestone=Config.GITLAB_DEFAULT_MILESTONE,
                            estimate_seconds=estimate_seconds
                        )
                        if gitlab_issue:
                            logger.info(f"  Created new GitLab issue #{gitlab_issue['iid']}: {gitlab_issue['title']}")
                            self.stats['created_issues'] += 1
                            if estimate_seconds:
                                self.stats['time_estimates_added'] += 1
                        else:
                            logger.error(f"  Failed to create GitLab issue")
                            self.stats['errors'] += 1
                            return
                    else:
                        logger.info(f"  Would create new GitLab issue: {ticket_name}")
                        if Config.ADD_TIME_ESTIMATES:
                            estimate = int(total_duration * Config.ESTIMATE_MULTIPLIER)
                            logger.info(f"    Would set time estimate: {self._format_duration(estimate)}")
                        self.stats['created_issues'] += 1  # Count for dry run
                else:
                    logger.info(f"  Skipping issue creation (AUTO_CREATE_ISSUES=false): {ticket_name}")
                    self.stats['skipped_entries'] += len(entries)
                    return
            else:
                logger.debug(f"  Skipping issue creation for generic description: {ticket_name}")
        
        # Sync time entries to GitLab issue
        if gitlab_issue:
            self._sync_entries_to_issue(gitlab_issue, entries)
        else:
            logger.info(f"  Skipping {len(entries)} entries - no GitLab issue to sync to")
            self.stats['skipped_entries'] += len(entries)
    
    def _should_create_issue(self, ticket_name: str) -> bool:
        """Determine if we should create a new issue based on the ticket name"""
        # Skip creating issues for very short descriptions
        if len(ticket_name.strip()) < Config.MIN_DESCRIPTION_LENGTH:
            logger.debug(f"Skipping short description: {ticket_name}")
            return False
        
        # Skip common generic terms
        for term in Config.SKIP_GENERIC_TERMS:
            if term.lower() in ticket_name.lower():
                logger.debug(f"Skipping generic term '{term}' in: {ticket_name}")
                return False
        
        return True
    
    def _sync_entries_to_issue(self, gitlab_issue: Dict, entries: List[Dict]):
        """Sync time entries to a specific GitLab issue"""
        total_logged_time = 0
        
        # Get existing time entries from GitLab to prevent duplicates (if enabled)
        existing_toggl_ids = set()
        if Config.PREVENT_DUPLICATES:
            try:
                existing_entries = self.gitlab_client.get_time_tracking_entries(gitlab_issue['iid'])
                logger.debug(f"Found {len(existing_entries)} existing time entries on issue #{gitlab_issue['iid']}")
                
                # Extract Toggl entry IDs from existing GitLab entries to detect duplicates
                for existing_entry in existing_entries:
                    summary = existing_entry.get('summary', '')
                    # Look for Toggl entry ID in summary (format: [TogglID:123456])
                    import re
                    match = re.search(r'\[TogglID:(\d+)\]', summary)
                    if match:
                        existing_toggl_ids.add(match.group(1))
                        
                logger.debug(f"Found {len(existing_toggl_ids)} existing Toggl entries already synced")
            except Exception as e:
                logger.warning(f"Could not fetch existing time entries for duplicate check: {e}")
        
        for entry in entries:
            try:
                # Check if this Toggl entry has already been synced (if duplicate prevention is enabled)
                toggl_id = str(entry['id'])
                if Config.PREVENT_DUPLICATES and toggl_id in existing_toggl_ids:
                    logger.info(f"    Skipping duplicate entry {toggl_id}: {entry['description']}")
                    self.stats['skipped_entries'] += 1
                    continue
                
                # Parse the start time
                start_time = datetime.fromisoformat(entry['start'].replace('Z', '+00:00'))
                
                # Create description for time log
                description_parts = [f"Toggl: {entry['description']}"]
                
                if entry.get('tags'):
                    description_parts.append(f"[Tags: {', '.join(entry['tags'])}]")
                
                if entry.get('billable'):
                    description_parts.append("[Billable]")
                
                if entry.get('original_duration') != entry['duration']:
                    original_time = self._format_duration(entry['original_duration'])
                    rounded_time = self._format_duration(entry['duration'])
                    description_parts.append(f"[Rounded: {original_time} → {rounded_time}]")
                
                # Add Toggl ID for duplicate detection (if enabled)
                if Config.PREVENT_DUPLICATES:
                    description_parts.append(f"[TogglID:{toggl_id}]")
                
                description = " ".join(description_parts)
                
                if not self.dry_run:
                    success = self.gitlab_client.add_time_spent(
                        issue_iid=gitlab_issue['iid'],
                        duration_seconds=entry['duration'],
                        spent_at=start_time,
                        description=description
                    )
                    
                    if success:
                        self.stats['synced_entries'] += 1
                        total_logged_time += entry['duration']
                        logger.info(f"    ✓ Logged {self._format_duration(entry['duration'])} to issue #{gitlab_issue['iid']}")
                    else:
                        self.stats['errors'] += 1
                else:
                    duration_str = self._format_duration(entry['duration'])
                    logger.info(f"    Would log {duration_str} on {start_time.date()}: {description}")
                    self.stats['synced_entries'] += 1
                    total_logged_time += entry['duration']
                    
            except Exception as e:
                logger.error(f"    Error syncing entry {entry['id']}: {e}")
                self.stats['errors'] += 1
        
        # Add time estimate if configured and not in dry run
        if Config.ADD_TIME_ESTIMATES and total_logged_time > 0 and not self.dry_run:
            try:
                estimate_seconds = int(total_logged_time * Config.ESTIMATE_MULTIPLIER)
                current_stats = self.gitlab_client.get_issue_time_stats(gitlab_issue['iid'])
                
                # Only set estimate if not already set
                if not current_stats.get('time_estimate'):
                    success = self.gitlab_client.set_time_estimate(gitlab_issue['iid'], estimate_seconds)
                    if success:
                        self.stats['time_estimates_added'] += 1
                        logger.info(f"    Set time estimate: {self._format_duration(estimate_seconds)}")
                        
            except Exception as e:
                logger.error(f"    Error setting time estimate: {e}")
        
        # Add summary note if multiple entries
        if len(entries) > 1 and not self.dry_run:
            total_time = self._format_duration(total_logged_time)
            summary_note = f"📊 Toggl Sync Summary: {len(entries)} entries totaling {total_time} logged from time tracking tool."
            try:
                self.gitlab_client.add_note_to_issue(gitlab_issue['iid'], summary_note)
            except Exception as e:
                logger.warning(f"Could not add summary note: {e}")
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to human readable format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        else:
            return f"{minutes}m"
    
    def _print_sync_summary(self):
        """Print sync operation summary"""
        logger.info("\n" + "="*50)
        logger.info("SYNC SUMMARY")
        logger.info("="*50)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE SYNC'}")
        logger.info(f"Processed entries: {self.stats['processed_entries']}")
        logger.info(f"Synced entries: {self.stats['synced_entries']}")
        logger.info(f"Created issues: {self.stats['created_issues']}")
        logger.info(f"Skipped entries: {self.stats['skipped_entries']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Total time synced: {self._format_duration(self.stats['total_time_synced'])}")
        logger.info(f"Billable time synced: {self._format_duration(self.stats['billable_time_synced'])}")
        
        if Config.ADD_TIME_ESTIMATES:
            logger.info(f"Time estimates added: {self.stats['time_estimates_added']}")
        
        logger.info("="*50)
        
        if self.dry_run:
            logger.info("This was a dry run. No actual changes were made.")
            logger.info("Set DRY_RUN=false in your .env file to perform actual sync.")
    
    def test_connections(self) -> bool:
        """Test connections to both Toggl and GitLab APIs"""
        logger.info("Testing API connections...")
        
        # Test Toggl connection
        try:
            projects = self.toggl_client.get_projects()
            user_info = self.toggl_client.get_user_info()
            workspace_info = self.toggl_client.get_workspace_info()
            
            logger.info(f"✓ Toggl connection successful")
            logger.info(f"  User: {user_info.get('fullname', 'Unknown')} ({user_info.get('email', 'N/A')})")
            logger.info(f"  Workspace: {workspace_info.get('name', 'Unknown')}")
            logger.info(f"  Projects available: {len(projects)}")
            
        except Exception as e:
            logger.error(f"✗ Toggl connection failed: {e}")
            return False
        
        # Test GitLab connection
        try:
            if not self.gitlab_client.test_connection():
                return False
            
            project_info = self.gitlab_client.get_project_info()
            logger.info(f"✓ GitLab connection successful")
            logger.info(f"  Project: {project_info.get('path_with_namespace', 'Unknown')}")
            logger.info(f"  Visibility: {project_info.get('visibility', 'Unknown')}")
            logger.info(f"  Issues enabled: {project_info.get('issues_enabled', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"✗ GitLab connection failed: {e}")
            return False
        
        return True 