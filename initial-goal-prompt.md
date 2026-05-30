You are a senior Site Reliability Engineer (SRE) and Cloud Architect specializing in AWS, GCP, observability systems, and AI-driven operations.

We are a cloud infrastructure team managing production systems across AWS and GCP. Our current pain points are:

- High volume of alerts from monitoring systems
- Manual triaging of incidents and logs
- Slow root cause analysis (RCA)
- Repetitive support tickets and escalations
- Lack of intelligent correlation between metrics, logs, and traces
- On-call fatigue

### 🎯 Objective
Design a complete AI adoption strategy to improve monitoring, incident response, and support operations using AI/LLM-based systems.

We want to move toward:

- AI-assisted alert triaging
- Automated incident summarization
- Intelligent log analysis and anomaly detection
- Root cause suggestions (RCA hints)
- Ticket auto-classification and routing
- ChatOps integration (Slack/Teams)
- Reduction of manual on-call workload

---

### 🧠 What you need to produce

1. **Current State Analysis**
   - Typical cloud monitoring stack assumptions (AWS CloudWatch, GCP Cloud Monitoring, Prometheus, Grafana, Datadog, etc.)
   - Where human intervention is currently required

2. **AI Use Cases for SRE / DevOps**
   Break down into:
   - Alert noise reduction
   - Incident summarization
   - Log clustering and anomaly detection
   - Root cause prediction
   - Auto-remediation suggestions
   - Ticket handling automation

3. **Architecture Design**
   Provide a reference architecture including:
   - AWS + GCP data ingestion layer
   - Observability pipeline (metrics, logs, traces)
   - AI/LLM layer (possible tools: OpenAI API / Bedrock / Vertex AI)
   - Event routing system (PagerDuty / Opsgenie / Slack)
   - Data storage and indexing (Elastic, OpenSearch, BigQuery, etc.)

4. **AI System Design**
   - How LLMs will be used (RAG, classification, summarization)
   - Prompt strategies for incidents
   - Context building from logs + metrics
   - Memory / historical incident learning

5. **Automation Workflows**
   Provide workflows like:
   - Alert → AI triage → severity classification → Slack summary
   - Incident → log aggregation → RCA suggestion → escalation decision
   - Ticket → AI classification → auto-routing to team

6. **Tooling Recommendations**
   Suggest:
   - AWS native tools
   - GCP native tools
   - Open-source stack options
   - AI/LLM integration tools

7. **Implementation Roadmap**
   Break into phases:
   - Phase 1: Observability foundation
   - Phase 2: AI-assisted insights
   - Phase 3: Semi-automation
   - Phase 4: Full autonomous remediation (where safe)

8. **Risks & Guardrails**
   - Hallucination risks in AI RCA
   - False automation risks
   - Security and access control
   - Production safety constraints

---

### 📌 Constraints
- Must be realistic for production-grade cloud environments
- Must work across both AWS and GCP
- Must prioritize reliability and safety over automation
- Prefer incremental adoption over “big bang” changes

---

### 🎯 Output format
- Use clear sections
- Include architecture diagrams in text form (ASCII or structured)
- Be actionable for an engineering team to start implementation immediately
