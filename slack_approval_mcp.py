# slack_approval_mcp.py (Fixed - 5 second max wait + Ignore Bot Messages)
import asyncio
import uuid
import json
import os
import re
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import mcp
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"

@dataclass
class ApprovalRequest:
    id: str
    operation: Dict[str, Any]
    timestamp: datetime
    status: ApprovalStatus
    context: str
    responded_by: Optional[str] = None
    response_time: Optional[datetime] = None

class SlackApprovalMCP:
    """MCP client for Slack-based human approval workflow."""
    
    def __init__(self, channel: str = "C09678WRA30", timeout_minutes: int = 5):
        self.channel = channel
        self.timeout_minutes = timeout_minutes
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.initialized = False
        self.bot_user_id = None  
        self.message_sent_timestamp = None  
        
    async def _get_bot_info(self, session: ClientSession) -> Optional[str]:
        """Get bot user ID to filter out bot messages."""
        try:        
            tools = await session.list_tools()
            return None
        except:
            return None
        
    async def request_approval(self, 
                             operation: Dict[str, Any], 
                             context: str) -> ApprovalRequest:
        """Send an approval request to Slack and wait for response."""
        
        approval_id = str(uuid.uuid4())[:8]  
        request = ApprovalRequest(
            id=approval_id,
            operation=operation,
            timestamp=datetime.now(),
            status=ApprovalStatus.PENDING,
            context=context
        )
        
        self.pending_approvals[approval_id] = request
        
        message_text = f"""🤖 Agent Approval Request

Request ID: {approval_id}
Context: {context}
Target: {operation.get('path', 'Unknown')}

To approve, reply: approve {approval_id}
To deny, reply: deny {approval_id}

This request will timeout in {self.timeout_minutes} minutes."""

        slack_token = os.getenv("SLACK_MCP_XOXP_TOKEN")
        slack_message_tool = os.getenv("SLACK_MCP_ADD_MESSAGE_TOOL")
        
        env = os.environ.copy()
        env.update({
            "SLACK_MCP_XOXP_TOKEN": slack_token,
            "SLACK_MCP_ADD_MESSAGE_TOOL": slack_message_tool
        })
        
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "slack-mcp-server@latest", "--transport", "stdio"],
            env=env
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                self.bot_user_id = await self._get_bot_info(session)
                
                tools = await session.list_tools()
                available_tools = [t.name for t in tools.tools]
                print(f"Available Slack tools: {available_tools}")
                
                self.message_sent_timestamp = datetime.now()
                
                try:
                    blocks = [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": "🤖 Agent Approval Request"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Request ID:* `{approval_id}`\n*Context:* {context}"
                            }
                        },
                        {
                            "type": "section",
                            "fields": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Operation:* `{operation.get('type', 'Unknown')}`"
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Target:* `{operation.get('path', 'Unknown')}`"
                                }
                            ]
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"⏰ *Timeout:* {self.timeout_minutes} minutes\n\nTo approve via text, reply: `approve {approval_id}`\nTo deny via text, reply: `deny {approval_id}`"
                            }
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "✅ Approve"
                                    },
                                    "style": "primary",
                                    "value": f"approve_{approval_id}"
                                },
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "❌ Deny"
                                    },
                                    "style": "danger",
                                    "value": f"deny_{approval_id}"
                                }
                            ]
                        }
                    ]
                    
                    try:
                        result = await session.call_tool(
                            "conversations_add_message",
                            arguments={
                                "channel_id": self.channel,
                                "payload": json.dumps({
                                    "blocks": blocks,
                                    "text": f"Approval Request {approval_id}: {operation.get('type', 'Unknown')} operation"  # Fallback text
                                }),
                                "content_type": "application/json"
                            }
                        )
                        print(f"Slack message sent successfully with buttons")
                    except Exception as block_error:
                        result = await session.call_tool(
                            "conversations_add_message",
                            arguments={
                                "channel_id": self.channel,
                                "payload": message_text,
                                "content_type": "text/plain"
                            }
                        )
                    
                except Exception as e:
                    try:
                        result = await session.call_tool(
                            "conversations_add_message",
                            arguments={
                                "channel": self.channel,
                                "text": message_text
                            }
                        )
                        print(f"Slack message sent with alternative format")
                    except Exception as e2:
                        try:
                            result = await session.call_tool(
                                "conversations_add_message",
                                arguments={
                                    "channel_id": self.channel,
                                    "payload": json.dumps({
                                        "text": message_text
                                    }),
                                    "content_type": "application/json"
                                }
                            )
                            print(f"Slack message sent with JSON format")
                        except Exception as e3:
                            raise Exception(f"All attempts failed: {str(e)}, {str(e2)}, {str(e3)}")
                
                await asyncio.sleep(1)
                
                return await self._wait_for_response(session, request)
    
    def _parse_csv_messages(self, csv_content: str) -> List[Dict[str, Any]]:
        """Parse CSV content into message dictionaries."""
        messages = []
        try:
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
            
            for row in reader:
                message = {
                    "user": row.get("UserID", ""),
                    "text": row.get("Text", ""),
                    "ts": row.get("Time", ""),
                    "username": row.get("UserName", ""),
                    "channel": row.get("Channel", "")
                }
                messages.append(message)
                
        except Exception as e:
            print(f"Error parsing CSV: {e}")
            
        return messages
    
    def _is_bot_message(self, message: Dict[str, Any]) -> bool:
        """Check if a message is from the bot itself."""
        if not isinstance(message, dict):
            return False
            
        user_id = message.get("user", "")
        username = message.get("username", "")
        
        if self.bot_user_id and user_id == self.bot_user_id:
            return True
            
        if "bot" in username.lower() or "app" in username.lower():
            return True
            
        text = message.get("text", "")
        if "Agent Approval Request" in text or "To approve, reply:" in text:
            return True
            
        if self.message_sent_timestamp and "ts" in message:
            try:
                msg_time = datetime.fromtimestamp(float(message["ts"]))
                time_diff = abs((msg_time - self.message_sent_timestamp).total_seconds())
                if time_diff < 5: 
                    return True
            except:
                pass
                
        return False
    
    async def _wait_for_response(self, session: ClientSession, request: ApprovalRequest) -> ApprovalRequest:
        """Wait for human response or timeout."""
        timeout_time = request.timestamp + timedelta(minutes=self.timeout_minutes)
        
        print(f"Waiting for approval response. Check Slack channel {self.channel}")
        print(f"Request ID to look for: {request.id}")
        print(f"Timeout at: {timeout_time.strftime('%H:%M:%S')}")
        
        seen_message_timestamps = set()
        check_interval = 3  
        
        while datetime.now() < timeout_time:
            try:
                result = await session.call_tool(
                    "conversations_history",
                    arguments={
                        "channel_id": self.channel,
                        "limit": "10"  
                    }
                )
                
                if hasattr(result, 'content'):
                    messages_data = result.content
                                        
                    if isinstance(messages_data, str):
                        if "UserID,UserName" in messages_data:
                            print("Detected CSV format, parsing...")
                            message_list = self._parse_csv_messages(messages_data)
                        else:
                            try:
                                messages_data = json.loads(messages_data)
                                message_list = messages_data.get('messages', []) if isinstance(messages_data, dict) else []
                            except:
                                print("Failed to parse as JSON, treating as plain text")
                                message_list = []
                    elif isinstance(messages_data, list):
                        if messages_data and hasattr(messages_data[0], 'text'):
                            csv_content = messages_data[0].text
                            if "UserID,UserName" in csv_content:
                                print("Detected CSV format in MCP text object, parsing...")
                                message_list = self._parse_csv_messages(csv_content)
                            else:
                                message_list = []
                        else:
                            message_list = messages_data
                    elif isinstance(messages_data, dict):
                        message_list = messages_data.get('messages', [])
                    else:
                        message_list = []
                    
                    print(f"Found {len(message_list)} messages")
                    
                    for i, message in enumerate(message_list):
                        if isinstance(message, dict):
                            msg_text = message.get('text', '')
                            msg_ts = message.get('ts', '')
                            msg_user = message.get('username', message.get('user', ''))
                        else:
                            msg_text = str(message)
                            msg_ts = ''
                            msg_user = ''
                        
                        if msg_ts and msg_ts in seen_message_timestamps:
                            continue
                            
                        if self._is_bot_message(message):
                            if msg_ts:
                                seen_message_timestamps.add(msg_ts)
                            continue
                        
                        print(f"Message {i} from {msg_user}: '{msg_text}'")
                        
                        is_approval = self._is_approval_response(message, request.id)
                        
                        if is_approval:
                            if msg_ts:
                                seen_message_timestamps.add(msg_ts)
                            request = self._process_response(message, request)
                            if request.status != ApprovalStatus.PENDING:
                                print(f"✅ Received response: {request.status.value}")
                                return request
                        elif msg_ts:
                            seen_message_timestamps.add(msg_ts)
                
            except Exception as e:
                error_msg = str(e)
                print(f"Error checking messages: {error_msg}")
                
                if "rate limit" in error_msg.lower():
                    import re
                    retry_match = re.search(r'retry after (\d+)([ms])', error_msg)
                    if retry_match:
                        retry_value = int(retry_match.group(1))
                        retry_unit = retry_match.group(2)
                        wait_time = retry_value * 60 if retry_unit == 'm' else retry_value
                        
                        wait_time = min(wait_time, 5)
                        
                        print(f"Rate limited. Waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"Rate limited. Waiting 5 seconds...")
                        await asyncio.sleep(5)
                        check_interval = 10
            
            remaining = (timeout_time - datetime.now()).total_seconds()
            if remaining > 0:
                print(f"Waiting... {int(remaining)} seconds remaining (checking every {check_interval}s)")
            
            await asyncio.sleep(check_interval)
        
        print("\nApproval request timed out")
        request.status = ApprovalStatus.TIMEOUT
        return request
    
    def _is_approval_response(self, message: Dict[str, Any], approval_id: str) -> bool:
        """Check if a message is a response to our approval request."""
        text = ""
        if isinstance(message, dict):
            text = message.get("text", "")
            if "attachments" in message:
                for attachment in message.get("attachments", []):
                    if "callback_id" in attachment and approval_id in attachment["callback_id"]:
                        return True
        elif isinstance(message, str):
            text = message
            
        print(f"Looking for approval_id: '{approval_id}'")
        
        text_lower = text.lower()
        approval_id_lower = approval_id.lower()
        
        has_approval_id = approval_id_lower in text_lower
        has_approve_word = "approve" in text_lower
        has_deny_word = "deny" in text_lower or "reject" in text_lower
                
        if has_approval_id and (has_approve_word or has_deny_word):
            return True
        
        if isinstance(message, dict) and "value" in message:
            value = str(message.get("value", ""))
            if approval_id in value:
                print("✅ Found button response!")
                return True
                
        return False
    
    def _process_response(self, message: Dict[str, Any], 
                         request: ApprovalRequest) -> ApprovalRequest:
        """Process an approval response message."""
        request.response_time = datetime.now()
        
        if isinstance(message, dict):
            request.responded_by = message.get("username", message.get("user", "unknown"))
            text = message.get("text", "")
        else:
            request.responded_by = "unknown"
            text = str(message)
            
        print(f"Processing response from {request.responded_by}: '{text}'")
        
        text_lower = text.lower()
        approval_id_lower = request.id.lower()
        
        if "approve" in text_lower and approval_id_lower in text_lower:
            request.status = ApprovalStatus.APPROVED
        elif ("deny" in text_lower or "reject" in text_lower) and approval_id_lower in text_lower:
            request.status = ApprovalStatus.DENIED
        else:
            print("⚠️ Could not determine approval status, keeping as PENDING")
        
        return request
