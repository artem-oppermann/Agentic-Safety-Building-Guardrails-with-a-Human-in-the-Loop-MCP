# orchestrator.py
import asyncio
import logging
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

from file_agent import FileManagementAgent, FileOperation
from slack_approval_mcp import SlackApprovalMCP, ApprovalStatus

@dataclass
class AuditLogEntry:
    timestamp: datetime
    operation: FileOperation
    required_approval: bool
    approval_status: Optional[ApprovalStatus] = None
    approved_by: Optional[str] = None
    execution_result: Optional[str] = None
    error: Optional[str] = None

class FileAgentOrchestrator:
    """Orchestrates file operations with human-in-the-loop safety checks."""
    
    def __init__(self, working_directory: str = "./agent-workspace"):
        self.agent = FileManagementAgent(working_directory)
        self.approval_system = SlackApprovalMCP()
        self.audit_log: List[AuditLogEntry] = []
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self):
        """Initialize all components."""
        self.logger.info("Orchestrator initialized with HITL safety checks")
    
    async def process_request(self, user_input: str) -> Dict[str, Any]:
        """Process a user request with appropriate safety checks."""
        log_entry = None
        try:
            # Parse the user's intent
            operation = await self.agent.parse_intent(user_input)
            
            # Create audit log entry
            log_entry = AuditLogEntry(
                timestamp=datetime.now(),
                operation=operation,
                required_approval=self.agent.is_high_risk_operation(operation)
            )
            
            # Decision tree for approval requirement
            if self.agent.is_high_risk_operation(operation):
                self.logger.info(f"High-risk operation detected: {operation.type}")
                
                # Create detailed context for approver
                context = self._create_approval_context(operation, user_input)
                
                try:
                    approval = await self.approval_system.request_approval(
                        operation.__dict__,
                        context
                    )
                    
                    log_entry.approval_status = approval.status
                    log_entry.approved_by = approval.responded_by
                    
                    if approval.status == ApprovalStatus.APPROVED:
                        self.logger.info(f"Operation approved by {approval.responded_by}")
                        result = await self._execute_with_fallback(operation)
                        log_entry.execution_result = "Success"
                        
                        # Add to audit log
                        self.audit_log.append(log_entry)
                        
                        return {
                            "success": True,
                            "result": result,
                            "required_approval": True,
                            "approval_status": "approved"
                        }
                    elif approval.status == ApprovalStatus.DENIED:
                        self.logger.info(f"Operation denied by {approval.responded_by}")
                        log_entry.execution_result = "Denied"
                        
                        # Add to audit log
                        self.audit_log.append(log_entry)
                        
                        return {
                            "success": False,
                            "error": "Operation denied by human reviewer",
                            "required_approval": True,
                            "approval_status": "denied"
                        }
                    else:  
                        self.logger.warning("Approval request timed out")
                        log_entry.execution_result = "Timeout"
                        
                        # Add to audit log
                        self.audit_log.append(log_entry)
                        
                        return {
                            "success": False,
                            "error": "Approval request timed out",
                            "required_approval": True,
                            "approval_status": "timeout"
                        }
                        
                except Exception as approval_error:
                    self.logger.error(f"Approval system error: {str(approval_error)}")
                    self.logger.error(traceback.format_exc())
                    log_entry.error = f"Approval system error: {str(approval_error)}"
                    
                    # Add to audit log
                    self.audit_log.append(log_entry)
                    
                    return {
                        "success": False,
                        "error": f"Failed to get approval: {str(approval_error)}",
                        "required_approval": True,
                        "approval_status": "error"
                    }
                    
            else:
                self.logger.info(f"Executing low-risk operation: {operation.type}")
                result = await self._execute_with_fallback(operation)
                log_entry.execution_result = "Success"
                
                # Add to audit log
                self.audit_log.append(log_entry)
                
                return {
                    "success": True,
                    "result": result,
                    "required_approval": False
                }
                
        except Exception as e:
            self.logger.error(f"Operation failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            if log_entry:
                log_entry.error = str(e)
                self.audit_log.append(log_entry)
            return {
                "success": False,
                "error": str(e),
                "required_approval": log_entry.required_approval if log_entry else False
            }
    
    def _create_approval_context(self, operation: FileOperation, 
                                user_input: str) -> str:
        """Create detailed context for the approval request."""
        context_parts = [
            f"User requested: \"{user_input}\"",
            f"\nThis translates to: {operation.type.value} operation",
            f"\nTarget path: {operation.path}"
        ]
        
        if operation.destination:
            context_parts.append(f"\nDestination: {operation.destination}")
        
        if operation.type.value == "delete":
            context_parts.append("\n\n⚠️ **Warning**: This will permanently delete the file/directory")
        elif operation.type.value == "move":
            context_parts.append("\n\n⚠️ **Warning**: This will move the file to a new location")
        elif operation.type.value == "write":
            context_parts.append("\n\n⚠️ **Warning**: This will overwrite any existing content")
        
        return "".join(context_parts)
    
    async def _execute_with_fallback(self, operation: FileOperation) -> Any:
        """Execute operation with error handling and fallback."""
        try:
            return await self.agent.execute_operation(operation)
        except Exception as e:
            self.logger.error(f"Primary execution failed: {e}")
            
            if operation.type.value == "delete":
                trash_path = f"trash/{datetime.now().isoformat()}_{operation.path}"
                try:
                    await self.agent._move_file(operation.path, trash_path)
                    return f"File moved to trash: {trash_path}"
                except:
                    raise e
            else:
                raise e
    
    def get_audit_log(self, 
                      start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Retrieve audit log entries within a date range."""
        filtered_logs = self.audit_log
        
        if start_date:
            filtered_logs = [log for log in filtered_logs 
                           if log.timestamp >= start_date]
        if end_date:
            filtered_logs = [log for log in filtered_logs 
                           if log.timestamp <= end_date]
        
        return [{
            "timestamp": log.timestamp.isoformat(),
            "operation": log.operation.type.value,
            "path": log.operation.path,
            "required_approval": log.required_approval,
            "approval_status": log.approval_status.value if log.approval_status else None,
            "approved_by": log.approved_by,
            "result": log.execution_result,
            "error": log.error
        } for log in filtered_logs]
