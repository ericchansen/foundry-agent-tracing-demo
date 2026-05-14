# Foundry Agent Tracing Demo — West Europe

Shows how to get agent traces working on a **classic Azure OpenAI resource** in **West Europe** with **DataZoneStandard** deployment.

> **Why this exists:** The Foundry portal doesn't have a Tracing page for classic Azure OpenAI resources. The Monitoring section only shows usage metrics. This repo shows how to route traces to Log Analytics instead, where you can query them with KQL.

## Quick start

### Option A: Azure Portal (no CLI needed)

1. **Create a Log Analytics workspace** — search "Log Analytics workspaces" in the Azure Portal > Create > pick your resource group and **West Europe**.

2. **Add diagnostic settings** — open your Azure OpenAI resource > **Monitoring > Diagnostic settings** > Add diagnostic setting. Enable these categories and send them to your Log Analytics workspace:
   - `Trace`
   - `RequestResponse`

3. **Run your agent**, wait 2–5 minutes, then go to your Log Analytics workspace > **Logs** and run:

   ```kql
   AzureDiagnostics
   | where Category == "Trace" or Category == "RequestResponse"
   | where TimeGenerated > ago(30m)
   | project TimeGenerated, Category, OperationName, ResultType, properties_s
   | order by TimeGenerated desc
   ```

### Option B: CLI + Python demo

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your values
python demo.py
```

This creates a test agent, runs it, and queries Log Analytics to verify traces arrived. See [`infra/setup.sh`](infra/setup.sh) to provision everything from scratch via CLI.

## Troubleshooting

| Problem | Fix |
|---|---|
| No traces in Log Analytics | Check that [diagnostic settings](https://learn.microsoft.com/en-us/azure/azure-monitor/essentials/diagnostic-settings) are configured with `Trace` and `RequestResponse` categories |
| No Tracing page in Foundry portal | Expected for classic resources — use Log Analytics KQL instead |
| Deployment fails with "SKU not available" | Use `DataZoneStandard`, not `Standard` — Standard doesn't exist in West Europe ([EU Data Zone boundary](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/data-privacy)) |
| Agent run fails with `server_error` / 0 tokens | gpt-5.4 doesn't support the Assistants API — use `gpt-4o` or `gpt-4.1` |
| `401` on API calls | If `disableLocalAuth` is true on your resource, use Azure AD auth (`DefaultAzureCredential`) instead of API keys |
| Traces don't appear immediately | Normal — there's a 2–5 minute ingestion delay |

## License

MIT
