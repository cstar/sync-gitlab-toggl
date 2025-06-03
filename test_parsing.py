#!/usr/bin/env python3
"""Test script for ticket parsing functionality."""

from toggl_client import TogglClient

def test_ticket_parsing():
    """Test the ticket parsing with various formats."""
    client = TogglClient('dummy', 'dummy')  # Dummy credentials for parsing only
    
    test_cases = [
        '#123: Fix login bug',
        'PROJ-456 Implement dashboard', 
        'Issue #789: Update docs',
        '[TICKET-321] Code review',
        'BUG-999 - Security fix',
        'General meeting',
        'ABC-123: Long task description with multiple words',
        '42 Simple numeric ticket',
        'No ticket format here'
    ]
    
    print('Testing ticket parsing:')
    print('-' * 60)
    
    for desc in test_cases:
        result = client.extract_ticket_info(desc)
        ticket_id = result['ticket_id'] or 'None'
        ticket_name = result['ticket_name']
        print(f'{desc:<35} -> ID: {ticket_id:<10} Name: {ticket_name}')

if __name__ == '__main__':
    test_ticket_parsing() 