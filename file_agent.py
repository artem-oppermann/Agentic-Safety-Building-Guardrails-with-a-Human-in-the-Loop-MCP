import os
import json
import shutil
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import openai
from datetime import datetime

class OperationType(Enum):
    LIST = "list"
    READ = "read"
    DELETE = "delete"
    MOVE = "move"
    WRITE = "write"

@dataclass
class FileOperation:
    type: OperationType
    path: str
    destination: Optional[str] = None
    content: Optional[str] = None

class FileManagementAgent:
    """A file management agent with built-in safety awareness and AI-driven operations."""
    
    def __init__(self, working_directory: str = "/home/artem/Schreibtisch/mcp/agent-workspace"):
        self.working_directory = os.path.abspath(working_directory)
        if not os.path.exists(self.working_directory):
            os.makedirs(self.working_directory)
        
        self.high_risk_operations = {
            OperationType.DELETE,
            OperationType.MOVE,
            OperationType.WRITE
        }
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def is_high_risk_operation(self, operation: FileOperation) -> bool:
        """Determine if an operation requires human approval."""
        return operation.type in self.high_risk_operations
    
    async def execute_operation(self, operation: FileOperation) -> Any:
        """Execute a file operation using AI-generated code."""
        full_path = self._get_full_path(operation.path)
        if not self._is_path_allowed(full_path):
            raise ValueError(f"Operation not allowed outside working directory: {full_path}")
        
        prompt = self._create_operation_prompt(operation, full_path)
        code_snippet = await self._get_ai_generated_code(prompt)
        print(f"AI-generated code: {code_snippet}")
        return await self._execute_code_snippet(code_snippet)
    
    def _get_full_path(self, path: str) -> str:
        """Resolve the full path within the working directory."""
        return os.path.abspath(os.path.join(self.working_directory, path))
    
    def _is_path_allowed(self, path: str) -> bool:
        """Check if the path is within the working directory."""
        return os.path.commonpath([path, self.working_directory]) == self.working_directory
    
    def _create_operation_prompt(self, operation: FileOperation, full_path: str) -> str:
        """Generate a prompt for AI to create operation code that sets 'result'."""
        base_prompt = (
            "Generate Python code that performs the following file operation and sets the result in a variable named 'result'. "
            "Use only standard Python libraries (os, shutil). Do not include imports in the code. "
            "Do not define any functions; write the code directly."
        )
        if operation.type == OperationType.LIST:
            return f"{base_prompt}\nList files in directory: {full_path}. Set 'result' to a list of filenames."
        if operation.type == OperationType.DELETE:
            return f"{base_prompt}\nDelete the file: {full_path}. Set 'result' to a success message or error message."
        # Add similar prompts for other operations as needed
        return base_prompt  # Fallback for unimplemented operations
    
    async def _get_ai_generated_code(self, prompt: str) -> str:
        """Get AI-generated code snippet."""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": "You are a Python code generator for file operations."
            }, {
                "role": "user",
                "content": prompt
            }]
        )
        code = response.choices[0].message.content.strip()
        # Remove any markdown code fences if present
        if code.startswith("```python") and code.endswith("```"):
            code = code[9:-3].strip()
        elif code.startswith("```") and code.endswith("```"):
            code = code[3:-3].strip()
        return code
    
    async def _execute_code_snippet(self, code: str) -> Any:
        """Safely execute the AI-generated code snippet."""
        safe_globals = {
            "os": os,
            "shutil": shutil
        }
        exec_locals = {}
        
        try:
            exec(code, safe_globals, exec_locals)
            return exec_locals.get("result")
        except Exception as e:
            raise Exception(f"Failed to execute AI-generated code: {e}\nCode: {code}")
    
    async def parse_intent(self, user_input: str) -> FileOperation:
        """Parse user intent into a file operation using OpenAI."""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": """You are an intent parser for file operations. Convert user input into a JSON object with:
                - type: one of 'list', 'read', 'delete', 'move', 'write'
                - path: string (relative to working directory)
                - destination: string (optional, for move, relative to working directory)
                - content: string (optional, for write)"""
            }, {
                "role": "user",
                "content": user_input
            }],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return FileOperation(
            type=OperationType(result["type"]),
            path=result["path"],
            destination=result.get("destination"),
            content=result.get("content")
        )
