#!/usr/bin/env python3
"""Cleanup script to remove duplicate time entries from GitLab issues"""

from gitlab_client import GitLabClient
from config import Config
import requests
import re
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_recent_time_notes(client, issue_id, days_back=7):
    """Get recent time tracking notes from an issue"""
    try:
        issue = client.project.issues.get(issue_id)
        notes = issue.notes.list(all=True)
        
        # Filter for recent time tracking system notes
        time_notes = []
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_back)
        
        for note in notes:
            body = note.body or ""
            created_at = datetime.fromisoformat(note.created_at.replace('Z', '+00:00'))
            
            # Look for system time tracking notes that are recent
            if ('added' in body and 'time spent' in body and created_at.date() >= cutoff_date.date()):
                time_notes.append({
                    'id': note.id,
                    'body': body,
                    'created_at': created_at,
                    'author': note.author.get('username') if hasattr(note, 'author') and note.author else 'System'
                })
                
        return time_notes
        
    except Exception as e:
        logger.error(f"Error getting notes for issue #{issue_id}: {e}")
        return []

def delete_time_spent(client, issue_id, duration, date_str):
    """Delete specific time spent from an issue"""
    try:
        # Use GitLab API to subtract time
        url = f"{client.gitlab_url}/api/v4/projects/{client.project_id}/issues/{issue_id}/add_spent_time"
        
        # Negative duration to subtract time
        data = {
            'duration': f"-{duration}",
            'spent_at': date_str,
            'summary': f"Removing duplicate time entry: {duration}"
        }
        
        response = requests.post(url, 
                               headers={'PRIVATE-TOKEN': client.api_token, 'Content-Type': 'application/json'}, 
                               json=data)
        
        if response.status_code in [200, 201]:
            logger.info(f"  ✓ Removed {duration} from issue #{issue_id}")
            return True
        else:
            logger.error(f"  ✗ Failed to remove {duration} from issue #{issue_id}: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error removing time from issue #{issue_id}: {e}")
        return False

def main():
    print("🧹 GitLab Time Entry Duplicate Cleanup Tool")
    print("=" * 50)
    
    # Initialize client
    client = GitLabClient(Config.GITLAB_URL, Config.GITLAB_TOKEN, Config.GITLAB_PROJECT_ID)
    
    # Issues to check (you can modify this list)
    issue_ids = [3, 10, 11]
    
    for issue_id in issue_ids:
        print(f"\n📋 Checking Issue #{issue_id}")
        print("-" * 30)
        
        try:
            issue = client.project.issues.get(issue_id)
            print(f"Issue: {issue.title}")
            
            # Get current time stats
            url = f"{Config.GITLAB_URL}/api/v4/projects/{Config.GITLAB_PROJECT_ID}/issues/{issue_id}/time_stats"
            response = requests.get(url, headers={'PRIVATE-TOKEN': Config.GITLAB_TOKEN})
            
            if response.status_code == 200:
                stats = response.json()
                total_time = stats.get('total_time_spent', 0)
                human_time = stats.get('human_total_time_spent', 'N/A')
                print(f"Current total time: {human_time} ({total_time}s)")
            
            # Get recent time tracking notes
            time_notes = get_recent_time_notes(client, issue_id, days_back=2)
            print(f"Found {len(time_notes)} recent time tracking notes")
            
            # Group by time duration and date to find duplicates
            time_groups = {}
            for note in time_notes:
                # Extract time and date from note
                body = note['body']
                created_date = note['created_at'].strftime('%Y-%m-%d')
                
                # Parse "added Xm of time spent" or "added Xh Ym of time spent"
                time_match = re.search(r'added ([0-9]+(?:h)?\s*[0-9]*m?) of time spent', body)
                if time_match:
                    duration = time_match.group(1).strip()
                    key = f"{duration}_{created_date}"
                    
                    if key not in time_groups:
                        time_groups[key] = []
                    time_groups[key].append(note)
            
            # Find and handle duplicates
            duplicates_found = False
            for key, notes in time_groups.items():
                if len(notes) > 1:
                    duplicates_found = True
                    duration = key.split('_')[0]
                    date = key.split('_')[1]
                    
                    print(f"  🔍 Found {len(notes)} entries for {duration} on {date}")
                    
                    # Keep the first one, remove the rest
                    for i, note in enumerate(notes[1:], 1):  # Skip first entry
                        print(f"    Removing duplicate #{i}: Note {note['id']} by {note['author']}")
                        
                        # Ask for confirmation
                        confirm = input(f"      Remove {duration} from {date}? (y/N): ").lower().strip()
                        if confirm == 'y':
                            success = delete_time_spent(client, issue_id, duration, date)
                            if not success:
                                print(f"      ⚠️  Failed to remove duplicate")
                        else:
                            print(f"      ⏭️  Skipped")
            
            if not duplicates_found:
                print("  ✅ No duplicates found")
                
        except Exception as e:
            print(f"  ❌ Error processing issue #{issue_id}: {e}")
    
    print(f"\n✨ Cleanup completed!")

if __name__ == "__main__":
    main() 