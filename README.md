# Agentic-Safety-Building-Guardrails-with-a-Human-in-the-Loop-MCP

# AI File Agent with Human-in-the-Loop Safety

An intelligent file management system that combines AI-powered automation with human oversight for safe file operations. The system uses OpenAI to understand natural language requests and executes file operations while requiring human approval for high-risk actions via Slack.

## Features

- **Natural Language Processing**: Convert plain English requests into file operations using OpenAI GPT-4
- **AI-Generated Code Execution**: Dynamically generates and executes Python code for file operations
- **Human-in-the-Loop Safety**: Requires human approval for high-risk operations (delete, move, write) via Slack
- **Comprehensive Audit Logging**: Tracks all operations, approvals, and outcomes with timestamps
- **Slack Integration**: Interactive approval workflow with buttons and fallback text commands
- **Sandboxed Operations**: All file operations are restricted to a designated working directory
- **Fallback Mechanisms**: Smart error handling with recovery options (e.g., move to trash instead of permanent delete)


## Installation

### Prerequisites

- Python 3.8+
- Node.js (for Slack MCP server)
- OpenAI API key
- Slack app with appropriate permissions

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ai-file-agent
   ```

2. **Install Python dependencies**
   ```bash
   pip install asyncio openai python-dotenv mcp
   ```

3. **Install Slack MCP server**
   ```bash
   npm install -g slack-mcp-server
   ```

4. **Configure environment variables**
   Create a `.env` file in the project root:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   SLACK_MCP_XOXP_TOKEN=your_slack_bot_token_here
   SLACK_MCP_ADD_MESSAGE_TOOL=true
   ```

5. **Set up Slack App**
   - Create a new Slack app at [api.slack.com](https://api.slack.com)
   - Add the following OAuth scopes:
     - `channels:history`
     - `channels:read`
     - `chat:write`
     - `users:read`
   - Install the app to your workspace
   - Copy the Bot User OAuth Token to your `.env` file

## Usage

### Basic Usage

```bash
python main.py
```

### Example Interactions

The system can handle natural language requests like:

- **Safe operations** (no approval needed):
  - "List all files in the directory"
  - "Show me the contents of config.txt"
  - "What files are in the logs folder?"

- **High-risk operations** (requires approval):
  - "Delete the old-backup.zip file"
  - "Move all .tmp files to the archive folder"
  - "Create a new configuration file with default settings"

### Approval Workflow

When a high-risk operation is detected:

1. **Slack Notification**: A formatted message is sent to the configured Slack channel
2. **Interactive Buttons**: Users can approve/deny with one click
3. **Text Commands**: Fallback text commands (`approve <request_id>` or `deny <request_id>`)
4. **Timeout Handling**: Requests automatically timeout after 5 minutes
5. **Audit Trail**: All decisions are logged with timestamps and user information

## Project Structure

```
ai-file-agent/
├── main.py                 # Entry point and demonstration
├── orchestrator.py         # Main orchestration logic with HITL safety
├── file_agent.py          # AI-powered file operations agent
├── slack_approval_mcp.py  # Slack integration for human approval
├── agent-workspace/       # Sandboxed working directory
├── .env                   # Environment variables (create this)
└── README.md             # This file
```

## Safety Features

### Risk Assessment
- **Low-risk operations**: List, read operations execute immediately
- **High-risk operations**: Delete, move, write operations require human approval

### Sandboxing
- All file operations are restricted to the `agent-workspace` directory
- Path traversal attacks are prevented with security checks

### Fallback Mechanisms
- Failed delete operations can fall back to moving files to trash
- Error handling with detailed logging for debugging

### Audit Trail
```python
# Get audit log with optional date filtering
audit_entries = orchestrator.get_audit_log(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31)
)
```

## Configuration

### Working Directory
```python
orchestrator = FileAgentOrchestrator(working_directory="./custom-workspace")
```

### Approval Timeout
```python
approval_system = SlackApprovalMCP(
    channel="C09678WRA30",  # Your Slack channel ID
    timeout_minutes=10      # Custom timeout
)
```

### High-Risk Operations
Customize which operations require approval by modifying `file_agent.py`:
```python
self.high_risk_operations = {
    OperationType.DELETE,
    OperationType.MOVE,
    OperationType.WRITE,
    # Add custom operations
}
```


## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
