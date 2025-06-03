# Toggl to GitLab Sync Tool

A Python script that synchronizes time entries from Toggl Track to GitLab issues. The tool can automatically extract ticket information from Toggl time entry descriptions and create corresponding GitLab issues with time tracking.

## Features

- 🔄 **Automatic Sync**: Fetches time entries from Toggl and pushes them to GitLab
- 🎫 **Smart Ticket Parsing**: Extracts ticket IDs and names from Toggl descriptions
- 📝 **Issue Creation**: Automatically creates GitLab issues when tickets don't exist
- 🕒 **Time Tracking**: Logs time spent on GitLab issues
- 🧪 **Dry Run Mode**: Test the sync without making actual changes
- 🏷️ **Flexible Parsing**: Supports multiple ticket ID formats (#123, PROJ-123, etc.)
- 📊 **Detailed Reporting**: Shows sync statistics and results

## Supported Ticket Formats

The tool can parse various ticket formats from Toggl descriptions:

- `#123: Task description`
- `PROJ-123 Task description`
- `Issue #123: Task description`
- `[PROJ-123] Task description`
- `PROJ-123 - Task description`

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd sync-gitlab-toggl
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp env.example .env
   # Edit .env with your API credentials
   ```

## Configuration

### Required Environment Variables

Create a `.env` file based on `env.example`:

```bash
# Toggl Track API Configuration
TOGGL_API_TOKEN=your_toggl_api_token_here
TOGGL_WORKSPACE_ID=your_workspace_id_here

# GitLab API Configuration
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your_gitlab_token_here
GITLAB_PROJECT_ID=your_project_id_here
```

### Optional Configuration

```bash
# Filter by specific Toggl project (leave empty for all projects)
TOGGL_PROJECT_ID=

# Number of days back to sync (default: 7)
SYNC_DAYS_BACK=7

# Run in dry-run mode by default (default: true)
DRY_RUN=true
```

### Getting API Credentials

#### Toggl Track API Token
1. Go to [https://track.toggl.com/profile](https://track.toggl.com/profile)
2. Scroll down to "API Token" section
3. Copy your API token

#### Toggl Workspace ID
1. Go to your Toggl workspace
2. The workspace ID is in the URL: `https://track.toggl.com/timer/{WORKSPACE_ID}`

#### GitLab Personal Access Token
1. Go to GitLab → Settings → Access Tokens
2. Create a new token with these scopes:
   - `api`
   - `read_user`
   - `read_repository` 
   - `write_repository`

#### GitLab Project ID
1. Go to your GitLab project
2. The project ID is displayed on the project's main page (numeric value)

## Usage

Make sure to activate your virtual environment first:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Basic Commands

**Test API connections**:
```bash
python main.py test
```

**Show current configuration**:
```bash
python main.py config
```

**Run sync in dry-run mode**:
```bash
python main.py sync --dry-run
```

**Run actual sync**:
```bash
python main.py sync
```

**Sync specific number of days**:
```bash
python main.py sync --days 14
```

**Test ticket parsing**:
```bash
python main.py parse-ticket "#123: Implement user authentication"
```

### CLI Options

- `--dry-run`: Run without making actual changes
- `--days N`: Override the number of days to sync back

## How It Works

1. **Fetch Time Entries**: Retrieves time entries from Toggl for the specified date range
2. **Parse Descriptions**: Extracts ticket IDs and names from time entry descriptions
3. **Find/Create Issues**: 
   - Searches for existing GitLab issues by ticket ID
   - Creates new issues if not found (and description is meaningful)
4. **Log Time**: Adds time tracking entries to the corresponding GitLab issues
5. **Report Results**: Shows detailed statistics of the sync operation

## Example Workflow

1. **In Toggl**, create time entries with descriptions like:
   - `#42: Fix login bug`
   - `PROJ-123 Add user dashboard`
   - `Issue #55: Update documentation`

2. **Test the parsing**:
   ```bash
   python main.py parse-ticket "#42: Fix login bug"
   ```

3. **Run the sync**:
   ```bash
   python main.py sync --dry-run  # Test first
   python main.py sync            # Actual sync
   ```

4. **Check GitLab**: Time entries will be logged on the corresponding issues

## Dry Run Mode

By default, the tool runs in dry-run mode to prevent accidental changes. In dry-run mode:

- ✅ Connects to APIs and fetches data
- ✅ Shows what changes would be made
- ❌ Does not create issues or log time
- ❌ Does not modify anything in GitLab

To disable dry-run mode, either:
- Set `DRY_RUN=false` in your `.env` file, or
- Don't use the `--dry-run` flag when calling `sync`

## Testing

**Test ticket parsing**:
```bash
python test_parsing.py
```

**Test API connections**:
```bash
python main.py test
```

**Run examples** (requires valid API credentials):
```bash
python example_usage.py
```

## Troubleshooting

### Common Issues

1. **API Connection Failed**:
   - Check your API tokens are correct
   - Verify workspace/project IDs
   - Ensure proper permissions for GitLab token

2. **No Time Entries Found**:
   - Check the date range (`SYNC_DAYS_BACK`)
   - Verify Toggl project ID filter if set
   - Ensure time entries exist in the specified period

3. **Issues Not Created**:
   - Check if descriptions are meaningful (>5 characters)
   - Verify GitLab permissions
   - Review dry-run output first

4. **ModuleNotFoundError**:
   - Make sure you activated the virtual environment: `source venv/bin/activate`
   - Reinstall dependencies: `pip install -r requirements.txt`

### Debug Tips

- Use `python main.py test` to verify connections
- Use `python main.py config` to check configuration
- Run with `--dry-run` first to see what would happen
- Check the detailed output for specific error messages

## Development

### Project Structure

```
sync-gitlab-toggl/
├── main.py              # CLI entry point
├── config.py            # Configuration management
├── toggl_client.py      # Toggl API client
├── gitlab_client.py     # GitLab API client
├── sync_service.py      # Main sync logic
├── requirements.txt     # Dependencies
├── env.example          # Environment variables template
├── test_parsing.py      # Test ticket parsing
├── example_usage.py     # Usage examples
└── README.md           # This file
```

### Running Tests

```bash
source venv/bin/activate
python test_parsing.py
python main.py parse-ticket "Your test description"
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is open source. See LICENSE file for details.

## Support

If you encounter issues or have questions:

1. Check the troubleshooting section above
2. Review the configuration carefully
3. Test with dry-run mode first
4. Open an issue with detailed error messages and configuration (without sensitive tokens) 