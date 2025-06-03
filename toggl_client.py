import requests
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import re
import pytz

logger = logging.getLogger(__name__)


class TogglClient:
    def __init__(self, api_token: str, workspace_id: str, user_id: Optional[str] = None):
        self.api_token = api_token
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.base_url = "https://api.track.toggl.com/api/v9"
        
        # Create basic auth header
        credentials = f"{api_token}:api_token"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Initialized Toggl client for workspace {workspace_id}")
    
    def get_time_entries(self, start_date: datetime, end_date: datetime, 
                        project_id: Optional[str] = None, 
                        only_billable: bool = False,
                        minimum_duration: int = 0) -> List[Dict]:
        """Fetch time entries from Toggl for a given date range"""
        # Use the correct API v9 endpoint for time entries
        url = f"{self.base_url}/me/time_entries"
        
        # Extend end_date by one day to ensure today's entries are included
        # since Toggl API might treat end_date as exclusive
        api_end_date = end_date + timedelta(days=1)
        
        params = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": api_end_date.strftime("%Y-%m-%d")
        }
        
        try:
            logger.info(f"Fetching time entries from {start_date.date()} to {end_date.date()}")
            logger.debug(f"API call: start_date={start_date.strftime('%Y-%m-%d')}, end_date={api_end_date.strftime('%Y-%m-%d')}")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            entries = response.json()
            logger.info(f"Retrieved {len(entries)} time entries from Toggl")
            
            # Filter entries to only include those within our actual date range
            # since we extended the API end_date
            filtered_entries = []
            for entry in entries:
                # Skip running timers
                if entry.get('duration', 0) <= 0:
                    continue
                
                # Check if entry is within our actual date range
                try:
                    entry_start = datetime.fromisoformat(entry['start'].replace('Z', '+00:00'))
                    if entry_start.date() > end_date.date():
                        logger.debug(f"Skipping entry {entry['id']} - beyond end date")
                        continue
                except Exception as e:
                    logger.warning(f"Could not parse date for entry {entry.get('id')}: {e}")
                    # Include entry if we can't parse the date
                
                # Filter by project if specified
                if project_id and str(entry.get('project_id', '')) != str(project_id):
                    logger.debug(f"Skipping entry {entry['id']} - different project")
                    continue
                
                # Filter by minimum duration
                if entry.get('duration', 0) < minimum_duration:
                    logger.debug(f"Skipping entry {entry['id']} - duration {entry['duration']}s below minimum {minimum_duration}s")
                    continue
                
                # Filter by billable status
                if only_billable and not entry.get('billable', False):
                    logger.debug(f"Skipping entry {entry['id']} - not billable")
                    continue
                
                # Filter by user ID if specified
                if self.user_id and str(entry.get('user_id')) != str(self.user_id):
                    logger.debug(f"Skipping entry {entry['id']} - different user")
                    continue
                
                filtered_entries.append(entry)
            
            logger.info(f"After filtering: {len(filtered_entries)} entries")
            return filtered_entries
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching time entries: {e}")
            return []
    
    def get_projects(self) -> List[Dict]:
        """Fetch all projects from the workspace"""
        url = f"{self.base_url}/workspaces/{self.workspace_id}/projects"
        
        try:
            logger.info("Fetching projects from Toggl")
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            projects = response.json()
            logger.info(f"Retrieved {len(projects)} projects")
            return projects
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching projects: {e}")
            return []
    
    def get_workspace_info(self) -> Dict:
        """Get workspace information"""
        url = f"{self.base_url}/workspaces/{self.workspace_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching workspace info: {e}")
            return {}
    
    def get_user_info(self) -> Dict:
        """Get current user information"""
        url = f"{self.base_url}/me"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching user info: {e}")
            return {}
    
    def extract_ticket_info(self, description: str) -> Dict[str, Optional[str]]:
        """
        Extract ticket information from Toggl time entry description
        Supports various formats like:
        - kazoo#123 description (project-specific format)
        - #123 description or #123: description
        - PROJ-123 Task description
        - Issue #123: Task description  
        - [PROJ-123] Task description
        - (PROJ-123) Task description
        - JIRA-123, ABC-456, etc.
        """
        if not description:
            return {"ticket_id": None, "ticket_name": None}
        
        # Enhanced patterns to match various ticket formats
        # Order matters - more specific patterns first
        patterns = [
            r'kazoo#(\d+)\s*(.*)',  # kazoo#123 description (your specific format)
            r'#(\d+):?\s*(.*)',  # #123: description or #123 description
            r'([A-Z]+-\d+):?\s*(.*)',  # PROJ-123: description or PROJ-123 description
            r'Issue\s+#(\d+):?\s*(.*)',  # Issue #123: description
            r'\[([A-Z]+-\d+)\]\s*(.*)',  # [PROJ-123] description
            r'\(([A-Z]+-\d+)\)\s*(.*)',  # (PROJ-123) description
            r'(\w+-\d+)\s*[-:]\s*(.*)',  # PROJ-123 - description or PROJ-123: description
            r'([A-Z]{2,}-\d+)\b\s*(.*)',  # JIRA-123 description (at word boundary)
            r'(\d+):\s*(.*)',  # 123: description (simple numeric)
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.match(pattern, description.strip(), re.IGNORECASE)
            if match:
                ticket_id = match.group(1)
                ticket_name = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else description
                
                logger.debug(f"Matched pattern {i+1} for '{description}' -> ID: {ticket_id}, Name: {ticket_name}")
                
                return {
                    "ticket_id": ticket_id,
                    "ticket_name": ticket_name or description
                }
        
        # If no pattern matches, return the full description as ticket name
        logger.debug(f"No ticket pattern matched for '{description}'")
        return {
            "ticket_id": None,
            "ticket_name": description
        }
    
    def round_time(self, duration_seconds: int, round_to_minutes: int = 15) -> int:
        """Round time duration to nearest specified minutes"""
        if round_to_minutes <= 0:
            return duration_seconds
        
        round_to_seconds = round_to_minutes * 60
        rounded = round(duration_seconds / round_to_seconds) * round_to_seconds
        
        # Ensure minimum of round_to_minutes
        if rounded == 0 and duration_seconds > 0:
            rounded = round_to_seconds
        
        logger.debug(f"Rounded {duration_seconds}s to {rounded}s (nearest {round_to_minutes}m)")
        return rounded
    
    def filter_by_weekdays(self, entries: List[Dict], exclude_weekends: bool = False) -> List[Dict]:
        """Filter entries to exclude weekends if specified"""
        if not exclude_weekends:
            return entries
        
        filtered = []
        for entry in entries:
            try:
                start_time = datetime.fromisoformat(entry['start'].replace('Z', '+00:00'))
                # Monday=0, Sunday=6
                if start_time.weekday() < 5:  # Monday to Friday
                    filtered.append(entry)
                else:
                    logger.debug(f"Skipping weekend entry: {entry['description']}")
            except Exception as e:
                logger.warning(f"Error parsing date for entry {entry.get('id')}: {e}")
                # Include entry if we can't parse the date
                filtered.append(entry)
        
        logger.info(f"Weekend filter: {len(entries)} -> {len(filtered)} entries")
        return filtered
    
    def process_time_entries(self, time_entries: List[Dict], 
                           minimum_duration: int = 0,
                           round_to_minutes: int = 15,
                           exclude_weekends: bool = False) -> List[Dict]:
        """Process time entries and extract ticket information with advanced filtering"""
        logger.info(f"Processing {len(time_entries)} time entries")
        
        # Apply weekend filter
        if exclude_weekends:
            time_entries = self.filter_by_weekdays(time_entries, exclude_weekends)
        
        processed_entries = []
        
        for entry in time_entries:
            try:
                # Skip running timers (negative duration)
                if entry.get('duration', 0) <= 0:
                    logger.debug(f"Skipping running timer: {entry.get('description', 'No description')}")
                    continue
                
                # Apply minimum duration filter
                if entry.get('duration', 0) < minimum_duration:
                    logger.debug(f"Skipping entry below minimum duration: {entry.get('description', 'No description')}")
                    continue
                
                # Extract ticket information
                ticket_info = self.extract_ticket_info(entry.get('description', ''))
                
                # Round time if specified
                original_duration = entry['duration']
                rounded_duration = self.round_time(original_duration, round_to_minutes)
                
                # Get project name if available
                project_name = None
                if entry.get('project_id'):
                    # This would require a separate API call to get project details
                    # For now, we'll just store the ID
                    project_name = f"Project {entry['project_id']}"
                
                processed_entry = {
                    'id': entry['id'],
                    'description': entry.get('description', ''),
                    'start': entry['start'],
                    'stop': entry.get('stop'),
                    'duration': rounded_duration,
                    'original_duration': original_duration,
                    'project_id': entry.get('project_id'),
                    'project_name': project_name,
                    'task_id': entry.get('task_id'),
                    'user_id': entry.get('user_id'),
                    'workspace_id': entry.get('workspace_id'),
                    'billable': entry.get('billable', False),
                    'ticket_id': ticket_info['ticket_id'],
                    'ticket_name': ticket_info['ticket_name'],
                    'tags': entry.get('tags', []),
                    'at': entry.get('at'),  # Last update time
                }
                
                processed_entries.append(processed_entry)
                
                if rounded_duration != original_duration:
                    logger.debug(f"Time rounded for entry {entry['id']}: {original_duration}s -> {rounded_duration}s")
                
            except Exception as e:
                logger.error(f"Error processing entry {entry.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Successfully processed {len(processed_entries)} entries")
        return processed_entries
    
    def get_detailed_stats(self, entries: List[Dict]) -> Dict:
        """Get detailed statistics about the time entries"""
        if not entries:
            return {}
        
        total_duration = sum(entry['duration'] for entry in entries)
        total_original = sum(entry.get('original_duration', entry['duration']) for entry in entries)
        billable_time = sum(entry['duration'] for entry in entries if entry.get('billable'))
        
        # Count entries by project
        projects = {}
        for entry in entries:
            proj_id = entry.get('project_id', 'No Project')
            if proj_id not in projects:
                projects[proj_id] = {'count': 0, 'duration': 0}
            projects[proj_id]['count'] += 1
            projects[proj_id]['duration'] += entry['duration']
        
        # Count entries with/without tickets
        with_tickets = sum(1 for entry in entries if entry.get('ticket_id'))
        without_tickets = len(entries) - with_tickets
        
        stats = {
            'total_entries': len(entries),
            'total_duration': total_duration,
            'total_original_duration': total_original,
            'time_saved_by_rounding': total_original - total_duration,
            'billable_time': billable_time,
            'non_billable_time': total_duration - billable_time,
            'entries_with_tickets': with_tickets,
            'entries_without_tickets': without_tickets,
            'projects': projects,
            'average_duration': total_duration / len(entries) if entries else 0,
        }
        
        return stats 