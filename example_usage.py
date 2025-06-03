#!/usr/bin/env python3
"""
Example usage of the Toggl to GitLab sync tool.

This script demonstrates how to use the sync functionality programmatically
instead of using the CLI interface.
"""

from datetime import datetime, timedelta
from sync_service import SyncService
from config import Config
from toggl_client import TogglClient


def example_basic_sync():
    """Example: Basic sync operation"""
    print("=== Basic Sync Example ===")
    
    try:
        # Initialize the sync service
        service = SyncService()
        
        # Test connections first
        if not service.test_connections():
            print("❌ Connection test failed!")
            return
        
        # Run the sync
        stats = service.sync_time_entries()
        
        print(f"Sync completed! Processed {stats['processed_entries']} entries.")
        
    except Exception as e:
        print(f"Error: {e}")


def example_custom_date_range():
    """Example: Sync with custom date range"""
    print("\n=== Custom Date Range Example ===")
    
    try:
        # Override the default sync period
        Config.SYNC_DAYS_BACK = 14  # Sync last 2 weeks
        
        service = SyncService()
        stats = service.sync_time_entries()
        
        print(f"Custom sync completed! Processed {stats['processed_entries']} entries.")
        
    except Exception as e:
        print(f"Error: {e}")


def example_ticket_parsing():
    """Example: Test ticket parsing functionality"""
    print("\n=== Ticket Parsing Example ===")
    
    # Create a Toggl client just for parsing (dummy credentials)
    client = TogglClient("dummy", "dummy")
    
    test_descriptions = [
        "#123: Fix login bug",
        "PROJ-456 Implement user dashboard", 
        "Issue #789: Update documentation",
        "[TICKET-321] Code review",
        "General meeting",  # No ticket format
        "BUG-999 - Critical security fix"
    ]
    
    for description in test_descriptions:
        result = client.extract_ticket_info(description)
        print(f"'{description}' -> ID: {result['ticket_id']}, Name: {result['ticket_name']}")


def example_dry_run():
    """Example: Run in dry-run mode"""
    print("\n=== Dry Run Example ===")
    
    try:
        # Enable dry-run mode
        Config.DRY_RUN = True
        
        service = SyncService()
        stats = service.sync_time_entries()
        
        print("Dry run completed - no actual changes were made!")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Run all examples
    example_basic_sync()
    example_custom_date_range()
    example_ticket_parsing()
    example_dry_run()
    
    print("\n✅ All examples completed!") 