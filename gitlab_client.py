import gitlab
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
import requests

logger = logging.getLogger(__name__)


class GitLabClient:
    def __init__(self, gitlab_url: str, api_token: str, project_id: str):
        self.gitlab_url = gitlab_url
        self.api_token = api_token
        self.project_id = project_id
        
        # Initialize GitLab connection with simpler, more reliable authentication
        try:
            # First, verify the token works with direct API calls
            logger.debug("Verifying GitLab token with direct API call...")
            test_response = requests.get(f"{gitlab_url}/api/v4/user",
                                       headers={'PRIVATE-TOKEN': api_token})
            
            if test_response.status_code != 200:
                raise Exception(f"GitLab token verification failed with status {test_response.status_code}: {test_response.text}")
            
            user_info = test_response.json()
            logger.info(f"GitLab token verified for user: {user_info.get('name', 'Unknown')} ({user_info.get('username', 'Unknown')})")
            
            # Now initialize the python-gitlab client
            logger.debug("Initializing python-gitlab client...")
            self.gl = gitlab.Gitlab(gitlab_url, private_token=api_token)
            
            # Test the connection
            self.gl.auth()
            self.project = self.gl.projects.get(project_id)
            
            logger.info(f"Successfully initialized GitLab client for project {project_id}")
                
        except Exception as e:
            logger.error(f"Failed to initialize GitLab client: {e}")
            logger.error(f"GitLab URL: {gitlab_url}")
            logger.error(f"Project ID: {project_id}")
            logger.error(f"Token length: {len(api_token)} characters")
            raise
    
    def test_connection(self) -> bool:
        """Test the GitLab connection"""
        try:
            # Test authentication
            self.gl.auth()
            # Test project access
            project_info = self.project.attributes
            logger.info(f"GitLab connection successful - Project: {project_info.get('path_with_namespace')}")
            return True
        except Exception as e:
            logger.error(f"GitLab connection test failed: {e}")
            return False
    
    def find_issue_by_ticket_id(self, ticket_id: str) -> Optional[Dict]:
        """Find GitLab issue by ticket ID (could be issue number or custom field)"""
        if not ticket_id:
            return None
        
        logger.debug(f"Searching for issue with ticket ID: {ticket_id}")
        
        try:
            # Try to find by issue IID (internal ID) if ticket_id is numeric
            if ticket_id.isdigit():
                try:
                    issue = self.project.issues.get(int(ticket_id))
                    logger.debug(f"Found issue by IID: #{issue.iid}")
                    return self._format_issue_dict(issue)
                except gitlab.exceptions.GitlabGetError:
                    logger.debug(f"No issue found with IID {ticket_id}")
            
            # Search by title containing the ticket ID
            issues = self.project.issues.list(
                search=ticket_id,
                in_='title',
                state='all',
                all=True
            )
            
            if issues:
                issue = issues[0]  # Take the first match
                logger.debug(f"Found issue by title search: #{issue.iid}")
                return self._format_issue_dict(issue)
            
            # Search by description containing the ticket ID
            issues = self.project.issues.list(
                search=ticket_id,
                in_='description',
                state='all',
                all=True
            )
            
            if issues:
                issue = issues[0]  # Take the first match
                logger.debug(f"Found issue by description search: #{issue.iid}")
                return self._format_issue_dict(issue)
            
            logger.debug(f"No issue found for ticket ID: {ticket_id}")
            
        except Exception as e:
            logger.error(f"Error finding issue {ticket_id}: {e}")
        
        return None
    
    def _format_issue_dict(self, issue) -> Dict:
        """Convert GitLab issue object to dict"""
        return {
            'id': issue.id,
            'iid': issue.iid,
            'title': issue.title,
            'description': issue.description,
            'state': issue.state,
            'web_url': issue.web_url,
            'assignees': [assignee.get('username') for assignee in issue.assignees] if hasattr(issue, 'assignees') else [],
            'labels': issue.labels if hasattr(issue, 'labels') else [],
            'milestone': issue.milestone.get('title') if hasattr(issue, 'milestone') and issue.milestone else None,
            'created_at': issue.created_at,
            'updated_at': issue.updated_at,
        }
    
    def create_issue(self, title: str, description: str = "", 
                    labels: List[str] = None, 
                    assignee: Optional[str] = None,
                    milestone: Optional[str] = None,
                    estimate_seconds: Optional[int] = None) -> Optional[Dict]:
        """Create a new GitLab issue with advanced options"""
        try:
            issue_data = {
                'title': title,
                'description': description or f"Auto-created from Toggl time tracking\n\nCreated by sync tool on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
            
            if labels:
                issue_data['labels'] = ','.join(labels)
            
            if assignee:
                # Find user by username
                try:
                    users = self.gl.users.list(username=assignee)
                    if users:
                        issue_data['assignee_id'] = users[0].id
                        logger.debug(f"Assigned issue to user: {assignee}")
                    else:
                        logger.warning(f"User not found: {assignee}")
                except Exception as e:
                    logger.warning(f"Error finding assignee {assignee}: {e}")
            
            if milestone:
                # Find milestone by title
                try:
                    milestones = self.project.milestones.list(search=milestone)
                    if milestones:
                        issue_data['milestone_id'] = milestones[0].id
                        logger.debug(f"Added milestone: {milestone}")
                    else:
                        logger.warning(f"Milestone not found: {milestone}")
                except Exception as e:
                    logger.warning(f"Error finding milestone {milestone}: {e}")
            
            # Add time estimate if provided
            if estimate_seconds:
                issue_data['time_estimate'] = estimate_seconds
            
            logger.info(f"Creating GitLab issue: {title}")
            issue = self.project.issues.create(issue_data)
            
            result = self._format_issue_dict(issue)
            logger.info(f"Created issue #{issue.iid}: {title}")
            return result
            
        except Exception as e:
            logger.error(f"Error creating issue '{title}': {e}")
            return None
    
    def add_time_spent(self, issue_iid: int, duration_seconds: int, spent_at: datetime, description: str = "") -> bool:
        """Add time spent to a GitLab issue"""
        try:
            # Convert seconds to GitLab time format (e.g., "1h 30m")
            time_spent = self._seconds_to_gitlab_time(duration_seconds)
            
            # Use direct API call instead of python-gitlab time_stats.create
            url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}/issues/{issue_iid}/add_spent_time"
            
            data = {
                'duration': time_spent,
                'summary': description[:255] if description else "Time logged from Toggl"
            }
            
            # Add spent_at if provided (some GitLab versions support this)
            if spent_at:
                data['spent_at'] = spent_at.strftime('%Y-%m-%d')
            
            logger.debug(f"Adding {time_spent} to issue #{issue_iid} via API")
            response = requests.post(url, 
                                   headers={'PRIVATE-TOKEN': self.api_token, 'Content-Type': 'application/json'}, 
                                   json=data)
            
            if response.status_code in [200, 201]:
                logger.info(f"Added {time_spent} to issue #{issue_iid}")
                
                # Add a manual note with TogglID for better duplicate tracking
                # Extract TogglID from description if present
                toggl_match = re.search(r'\[TogglID:(\d+)\]', description)
                if toggl_match:
                    toggl_id = toggl_match.group(1)
                    note_text = f"🕒 Time logged: {time_spent} on {spent_at.strftime('%Y-%m-%d')} - {description}"
                    try:
                        self.add_note_to_issue(issue_iid, note_text)
                        logger.debug(f"Added tracking note for TogglID {toggl_id}")
                    except Exception as e:
                        logger.warning(f"Could not add tracking note: {e}")
                
                return True
            else:
                logger.error(f"Failed to add time to issue #{issue_iid}: HTTP {response.status_code} - {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"Error adding time to issue #{issue_iid}: {e}")
            return False
    
    def set_time_estimate(self, issue_iid: int, estimate_seconds: int) -> bool:
        """Set time estimate for a GitLab issue"""
        try:
            # Convert seconds to GitLab time format
            estimate_time = self._seconds_to_gitlab_time(estimate_seconds)
            
            # Use direct API call for setting time estimate
            url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}/issues/{issue_iid}/time_estimate"
            
            data = {
                'duration': estimate_time
            }
            
            logger.debug(f"Setting time estimate {estimate_time} for issue #{issue_iid}")
            response = requests.post(url, 
                                   headers={'PRIVATE-TOKEN': self.api_token, 'Content-Type': 'application/json'}, 
                                   json=data)
            
            if response.status_code in [200, 201]:
                logger.info(f"Set time estimate for issue #{issue_iid}: {estimate_time}")
                return True
            else:
                logger.error(f"Failed to set time estimate for issue #{issue_iid}: HTTP {response.status_code} - {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"Error setting time estimate for issue #{issue_iid}: {e}")
            return False
    
    def _seconds_to_gitlab_time(self, seconds: int) -> str:
        """Convert seconds to GitLab time format (e.g., '1h 30m')"""
        if seconds <= 0:
            return "1m"  # Minimum time
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        time_parts = []
        if hours > 0:
            time_parts.append(f"{hours}h")
        if minutes > 0:
            time_parts.append(f"{minutes}m")
        
        return " ".join(time_parts) if time_parts else "1m"
    
    def get_issue_time_stats(self, issue_iid: int) -> Dict:
        """Get time statistics for a GitLab issue"""
        try:
            # Use direct API call to get time stats
            url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}/issues/{issue_iid}/time_stats"
            
            response = requests.get(url, headers={'PRIVATE-TOKEN': self.api_token})
            
            if response.status_code == 200:
                time_stats = response.json()
                return {
                    'time_estimate': time_stats.get('time_estimate', 0),
                    'total_time_spent': time_stats.get('total_time_spent', 0),
                    'human_time_estimate': time_stats.get('human_time_estimate', ''),
                    'human_total_time_spent': time_stats.get('human_total_time_spent', '')
                }
            else:
                logger.debug(f"Could not get time stats for issue #{issue_iid}: HTTP {response.status_code}")
                return {}
            
        except Exception as e:
            logger.error(f"Error getting time stats for issue #{issue_iid}: {e}")
            return {}
    
    def get_time_tracking_entries(self, issue_iid: int) -> List[Dict]:
        """Get all time tracking entries for an issue"""
        try:
            formatted_entries = []
            
            # Method 1: Check for our manual tracking notes with TogglID
            try:
                issue = self.project.issues.get(issue_iid)
                notes = issue.notes.list(all=True, per_page=100)
                logger.debug(f"Found {len(notes)} notes to check for time entries on issue #{issue_iid}")
                
                for note in notes:
                    body = note.body or ""
                    
                    # Look for our specific tracking notes with emoji and TogglID
                    if ('🕒 Time logged:' in body and '[TogglID:' in body) or \
                       ('[TogglID:' in body and ('Toggl:' in body or 'time logged' in body.lower())):
                        
                        # Extract Toggl ID
                        toggl_match = re.search(r'\[TogglID:(\d+)\]', body)
                        if toggl_match:
                            formatted_entries.append({
                                'id': note.id,
                                'summary': body,
                                'toggl_id': toggl_match.group(1),
                                'created_at': note.created_at,
                                'user': note.author.get('username') if hasattr(note, 'author') and note.author else None,
                                'type': 'tracking_note'
                            })
                            logger.debug(f"Found Toggl tracking note for ID {toggl_match.group(1)} in note {note.id}")
                
                logger.debug(f"Found {len(formatted_entries)} existing Toggl time entries via tracking notes")
                
            except Exception as e:
                logger.debug(f"Could not get time entries via notes: {e}")
            
            # Method 2: Look for older format in summary notes (fallback)
            try:
                issue = self.project.issues.get(issue_iid)
                notes = issue.notes.list(all=True, per_page=100)
                
                for note in notes:
                    body = note.body or ""
                    
                    # Look for older format summary notes that might contain TogglID
                    if '📊 Toggl Sync Summary:' in body:
                        # These are summary notes, might contain multiple TogglIDs in the future
                        logger.debug(f"Found Toggl sync summary note: {note.id}")
                        # For now, we don't extract individual IDs from summary notes
                
            except Exception as e:
                logger.debug(f"Could not check summary notes: {e}")
            
            # Method 3: Try direct API call to get time tracking events (if available)
            try:
                events_url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}/issues/{issue_iid}/resource_time_events"
                response = requests.get(events_url, headers={'PRIVATE-TOKEN': self.api_token})
                
                if response.status_code == 200:
                    events = response.json()
                    logger.debug(f"Found {len(events)} time events via API")
                    
                    for event in events:
                        # Look for our Toggl ID in the summary
                        summary = event.get('summary', '')
                        toggl_match = re.search(r'\[TogglID:(\d+)\]', summary)
                        if toggl_match:
                            # Avoid duplicates from notes method
                            toggl_id = toggl_match.group(1)
                            if not any(entry.get('toggl_id') == toggl_id for entry in formatted_entries):
                                formatted_entries.append({
                                    'id': event.get('id'),
                                    'summary': summary,
                                    'toggl_id': toggl_id,
                                    'created_at': event.get('created_at'),
                                    'user': event.get('user', {}).get('username') if event.get('user') else None,
                                    'type': 'time_event'
                                })
                                logger.debug(f"Found Toggl entry {toggl_id} in time event {event.get('id')}")
                else:
                    logger.debug(f"Time events API returned {response.status_code}")
                    
            except Exception as e:
                logger.debug(f"Could not get time events via API: {e}")
            
            total_found = len(formatted_entries)
            logger.debug(f"Total existing Toggl time entries found: {total_found}")
            
            # Return unique entries based on toggl_id
            unique_entries = {}
            for entry in formatted_entries:
                toggl_id = entry.get('toggl_id')
                if toggl_id and toggl_id not in unique_entries:
                    unique_entries[toggl_id] = entry
            
            result = list(unique_entries.values())
            logger.debug(f"Returning {len(result)} unique Toggl entries for duplicate check")
            return result
            
        except Exception as e:
            logger.error(f"Error getting time entries for issue #{issue_iid}: {e}")
            return []
    
    def search_issues(self, query: str, state: str = 'all', labels: List[str] = None) -> List[Dict]:
        """Search for issues in the project"""
        try:
            search_params = {
                'search': query,
                'state': state,
                'all': True
            }
            
            if labels:
                search_params['labels'] = ','.join(labels)
            
            logger.debug(f"Searching issues with query: {query}")
            issues = self.project.issues.list(**search_params)
            
            return [self._format_issue_dict(issue) for issue in issues]
            
        except Exception as e:
            logger.error(f"Error searching issues: {e}")
            return []
    
    def get_project_info(self) -> Dict:
        """Get basic project information"""
        try:
            project_dict = {
                'id': self.project.id,
                'name': self.project.name,
                'description': self.project.description,
                'web_url': self.project.web_url,
                'namespace': self.project.namespace.get('name', ''),
                'path_with_namespace': self.project.path_with_namespace,
                'default_branch': self.project.default_branch,
                'visibility': self.project.visibility,
                'issues_enabled': self.project.issues_enabled,
                'created_at': self.project.created_at,
                'last_activity_at': self.project.last_activity_at,
            }
            
            # Get additional stats
            try:
                project_dict['open_issues_count'] = self.project.open_issues_count
                project_dict['star_count'] = self.project.star_count
                project_dict['forks_count'] = self.project.forks_count
            except:
                pass  # Some GitLab instances might not have these fields
            
            return project_dict
            
        except Exception as e:
            logger.error(f"Error getting project info: {e}")
            return {}
    
    def get_milestones(self) -> List[Dict]:
        """Get all milestones for the project"""
        try:
            milestones = self.project.milestones.list(all=True)
            return [{
                'id': milestone.id,
                'title': milestone.title,
                'description': milestone.description,
                'state': milestone.state,
                'due_date': milestone.due_date,
                'web_url': milestone.web_url,
            } for milestone in milestones]
        except Exception as e:
            logger.error(f"Error getting milestones: {e}")
            return []
    
    def get_labels(self) -> List[Dict]:
        """Get all labels for the project"""
        try:
            labels = self.project.labels.list(all=True)
            return [{
                'id': label.id,
                'name': label.name,
                'description': label.description,
                'color': label.color,
            } for label in labels]
        except Exception as e:
            logger.error(f"Error getting labels: {e}")
            return []
    
    def create_label(self, name: str, color: str = '#428BCA', description: str = '') -> bool:
        """Create a new label"""
        try:
            self.project.labels.create({
                'name': name,
                'color': color,
                'description': description
            })
            logger.info(f"Created label: {name}")
            return True
        except Exception as e:
            logger.error(f"Error creating label {name}: {e}")
            return False
    
    def add_note_to_issue(self, issue_iid: int, note: str) -> bool:
        """Add a note/comment to an issue"""
        try:
            issue = self.project.issues.get(issue_iid)
            issue.notes.create({'body': note})
            logger.info(f"Added note to issue #{issue_iid}")
            return True
        except Exception as e:
            logger.error(f"Error adding note to issue #{issue_iid}: {e}")
            return False 