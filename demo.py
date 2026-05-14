"""
Foundry Agent Tracing Demo — West Europe (Classic Resource)

Demonstrates:
  - Creating an Azure AI Foundry agent using the Assistants API
  - Running a conversation thread
  - Verifying trace data lands in Log Analytics

Requirements: pip install -r requirements.txt
Auth: az login (uses DefaultAzureCredential — no API key needed)
"""

import os
import time
import sys
import warnings
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

# The openai SDK marks the Assistants API as deprecated in favour of the
# Responses API, but Azure AI Foundry still uses the Assistants/Agents surface.
# Suppress those SDK-level warnings so demo output stays readable.
warnings.filterwarnings("ignore", category=DeprecationWarning)

load_dotenv()

ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
API_VERSION = "2024-05-01-preview"

# ------------------------------------------------------------------
# Client setup — uses Azure AD (works even when disableLocalAuth=true)
# ------------------------------------------------------------------
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    azure_endpoint=ENDPOINT,
    azure_ad_token_provider=token_provider,
    api_version=API_VERSION,
)


def run_agent_demo(user_message: str = "What is the capital of Belgium, and what is 12 * 7?") -> str:
    """Create a one-shot agent run and return the assistant reply."""

    print(f"\n{'='*60}")
    print(f"Endpoint : {ENDPOINT}")
    print(f"Deployment: {DEPLOYMENT}")
    print(f"Question  : {user_message}")
    print("=" * 60)

    # 1. Create agent
    print("\n[1/4] Creating agent...")
    agent = client.beta.assistants.create(
        model=DEPLOYMENT,
        name="trace-demo-agent",
        instructions="You are a helpful assistant. Answer concisely.",
    )
    print(f"      Agent ID: {agent.id}")

    try:
        # 2. Create thread + message
        print("\n[2/4] Creating thread and message...")
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message,
        )
        print(f"      Thread ID: {thread.id}")

        # 3. Run
        print("\n[3/4] Starting run...")
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=agent.id,
        )
        print(f"      Run ID: {run.id}")

        # Poll until terminal state
        timeout = 60
        start = time.time()
        while run.status in ("queued", "in_progress"):
            if time.time() - start > timeout:
                print("      Timed out waiting for run.")
                break
            time.sleep(2)
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id
            )
            print(f"      Status: {run.status}")

        if run.status != "completed":
            err = getattr(run, "last_error", None)
            raise RuntimeError(f"Run ended with status '{run.status}': {err}")

        # 4. Get reply
        print("\n[4/4] Fetching reply...")
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        reply = next(
            (
                m.content[0].text.value
                for m in messages.data
                if m.role == "assistant"
            ),
            "(no reply)",
        )
        print(f"\nAgent reply: {reply}")
        return reply

    finally:
        # Clean up agent so the resource stays tidy
        client.beta.assistants.delete(agent.id)
        print(f"\nCleaned up agent {agent.id}")


def check_traces(workspace_id: str, run_id: str | None = None, wait_minutes: int = 3) -> None:
    """
    Query Log Analytics for Trace entries from the OpenAI resource.
    Traces can take 2-5 minutes to appear after a run completes.
    """
    from azure.monitor.query import LogsQueryClient
    from azure.monitor.query import LogsQueryStatus
    import datetime

    print(f"\n{'='*60}")
    print(f"Checking Log Analytics for traces (workspace: {workspace_id})")
    print(f"Waiting {wait_minutes} min for ingestion delay...")
    print("=" * 60)
    time.sleep(wait_minutes * 60)

    logs_client = LogsQueryClient(credential)

    # KQL: look for Trace category in last 30 minutes
    query = """
AzureDiagnostics
| where Category == "Trace" or Category == "RequestResponse"
| where TimeGenerated > ago(30m)
| project TimeGenerated, Category, OperationName, ResultType, properties_s
| order by TimeGenerated desc
| take 20
"""
    result = logs_client.query_workspace(
        workspace_id=workspace_id,
        query=query,
        timespan=datetime.timedelta(hours=1),
    )

    if result.status == LogsQueryStatus.SUCCESS:
        rows = result.tables[0].rows if result.tables else []
        if rows:
            print(f"\n✅ Found {len(rows)} trace entries in Log Analytics!\n")
            for row in rows[:5]:
                print(f"  {row}")
        else:
            print("\n⚠️  No trace rows yet. Try waiting a few more minutes.")
            print("   Tip: Check that diagnostic settings include the 'Trace' category.")
    else:
        print(f"\n❌ Query error: {result.partial_error}")


if __name__ == "__main__":
    reply = run_agent_demo()

    workspace_id = os.environ.get("LOG_ANALYTICS_WORKSPACE_ID")
    if workspace_id:
        check_traces(workspace_id, wait_minutes=3)
    else:
        print("\nℹ️  Set LOG_ANALYTICS_WORKSPACE_ID in .env to verify trace ingestion.")
        print("   Workspace ID (customerId):")
        print("   az monitor log-analytics workspace show -g <rg> -n <name> --query customerId -o tsv")
