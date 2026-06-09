# Session Notes — 2026-06-09 — Pain Points & Pickup Items

## Pain Points Found During Testing

### P1 — S012 (PostgreSQL) KB match not working in live agent [HIGH]
- **Issue:** `_load_kb()` in `classifier_dev.py` reads the correct file (13 solutions, S012 present) but the running uvicorn process returns "No KB match" for postgresql alerts
- **Root cause:** Under investigation — `_load_kb()` is called per-request (no caching now) but the debug log line never fires in the running process, suggesting the function body isn't executing as expected in the uvicorn process context
- **Workaround:** Frontend and Backend alerts work correctly (S001b match), only PostgreSQL (S012) affected
- **Next session:** Add `print()` to stdout in `_load_kb()`, check if `__file__` resolves differently in uvicorn worker vs. direct Python invocation

### P2 — AWS session expires every ~1 hour [MEDIUM]
- **Issue:** AWS credentials expire (IAM role session), breaking Bedrock LLM calls and SSM commands mid-test
- **Impact:** LLM fallback silently fails (returns escalate with 0% confidence), SSM commands fail
- **Fix needed:** Store longer-lived credentials or add auto-refresh logic in dev_env

### P3 — SSM execution not yet wired end-to-end [MEDIUM]
- **Issue:** `ssm_executor.py` is built but `_execute_action_async` is added to `dev_app.py` — however, never actually tested executing a live SSM command because S012 issue blocked the PostgreSQL test
- **What works:** Frontend and Backend approvals trigger `_execute_action_async` which calls `execute_approved_action` → but needs live test to confirm SSM runs correctly
- **Next session:** Stop services, approve, verify SSM actually restarts them (check `systemctl is-active` after approval)

### P4 — Resolved alerts create new approval instead of closing existing [LOW]
- **Issue:** When a "resolved" status alert is fired, it creates a new `human-approval-required` instead of updating/closing the original incident
- **Fix:** Check `alert.status == "resolved"` in `dev_app.py` and skip approval creation, instead update the existing incident record

---

## What's Working ✅
- KB classification: 12/13 patterns (all except S012 in live agent)
- LLM fallback: 15/15 test cases (KB series + LLM series + variations)
- Human approval system: full flow working end-to-end
- ApprovalDetail panel: action preview with commands/emails
- React UI: Dashboard, All Alerts, Approvals pages with light/dark theme
- Express+SQLite backend: incidents and approvals persisted
- SSM stop commands: working (services confirmed stopped)

## Pickup Checklist for Tomorrow
1. [ ] Fix P1: Debug S012 KB match in uvicorn process (add `print()` to `_load_kb`, compare `__file__` in worker vs direct)
2. [ ] Fix P4: Skip approval for resolved alerts
3. [ ] Test P3: Live SSM restart — stop postgresql, approve, verify `systemctl is-active postgresql` returns `active`
4. [ ] Push all changes to git (classifier_dev.py, ssm_executor.py, dev_app.py, agent/known-solutions.json)
5. [ ] Update PROGRESS.md and CLAUDE.md with today's session

## Resume Command
```
Read CLAUDE.md in Cloud-AeonX-Digital/cloud-ai-adoption.
Check PROGRESS.md and dev_env/SESSION-NOTES.md for last session context.
Fix P1 (S012 KB match), then test SSM execution end-to-end.
```
