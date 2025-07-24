# main.py
import asyncio
import logging
import os
from orchestrator import FileAgentOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def demonstrate_agent():
    """Demonstrate the file agent with HITL safety features."""
    
    # Initialize the orchestrator
    orchestrator = FileAgentOrchestrator()
    await orchestrator.initialize()
    
    # Test scenarios
    test_cases = [
        # Safe operations (no approval needed)
        "List all files in the directory",
        
        # High-risk operations (approval required)
        "Delete the old-backup.zip file"
    ]
    
    for test_input in test_cases:
        print(f"\n{'='*60}")
        print(f"User Request: {test_input}")
        print(f"{'='*60}")
        
        result = await orchestrator.process_request(test_input)
        
        if result["success"]:
            print(f"\n✅ Operation completed successfully")
            if result["required_approval"]:
                print(f"   Approval Status: {result['approval_status']}")
            print(f"   Result: {result['result']}")
        else:
            print(f"❌ Operation failed")
            print(f"   Error: {result['error']}")
            if result["required_approval"]:
                print(f"   Approval Status: {result.get('approval_status', 'N/A')}")
    
    # Display audit log
    print(f"\n{'='*60}")
    print("AUDIT LOG")
    print(f"{'='*60}")
    
    audit_entries = orchestrator.get_audit_log()
    for entry in audit_entries:
        print(f"\nTimestamp: {entry['timestamp']}")
        print(f"Operation: {entry['operation']} on {entry['path']}")
        print(f"Required Approval: {entry['required_approval']}")
        if entry['required_approval']:
            print(f"Approval Status: {entry['approval_status']}")
            print(f"Approved By: {entry['approved_by']}")
        print(f"Result: {entry['result']}")

if __name__ == "__main__":
    # Set up environment variables if using .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("Loaded .env file")
    except ImportError:
        print("python-dotenv not installed. Using system environment variables.")
    
    # Verify critical environment variables
    if not os.getenv("SLACK_MCP_ADD_MESSAGE_TOOL"):
        print("WARNING: SLACK_MCP_ADD_MESSAGE_TOOL not set. Setting to channel C09678WRA30")
        os.environ["SLACK_MCP_ADD_MESSAGE_TOOL"] = "C09678WRA30"
    
    asyncio.run(demonstrate_agent())
