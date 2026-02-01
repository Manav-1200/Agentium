# 🏛️ Agentium

> A local-first AI governance platform where AI agents operate like a democratic government

Agentium transforms AI task management into a structured democracy. Your AI system mirrors a government hierarchy: a **Head of Council** (Prime Minister), **Council Members** (Parliament), and **Agents** (civil servants) work together to handle your tasks efficiently and transparently.

It is a fully Dockerized, cross-platform AI system that runs on any computer, offering a complete web-based interface for control, monitoring, and governance, while also supporting command execution through channels like WhatsApp, Telegram, and more using a democratic, council-governed hierarchy of AI agents for safe, auditable automation.


![Development Status](https://img.shields.io/badge/status-active--development-brightgreen)


---

## ✨ What Makes Agentium Special?

**Democratic AI Governance** — Tasks aren't just executed; they're deliberated, voted on, and approved through a multi-tier AI system that ensures accountability.

**Local-First Philosophy** — Run everything on your own hardware with full control over your data and models.

**Intelligent Scaling** — The system automatically spawns new agents and council members as workload increases.

**Universal Access** — Control everything from a sleek web dashboard accessible on any device.

---

## 🎯 Core Capabilities

### Hybrid AI Models
Run powerful local models (Kimi 2.5, GPT-4) or leverage API services (Anthropic, OpenAI, Gemini) based on your needs and resources.

### Hierarchical AI System

```
👑 You (The Sovereign)
    ↓
🏛️ Head of Council — Full authority, approves/rejects major decisions
    ↓
⚖️ Council Members — Deliberate and vote on proposals
    ↓
🎯 Lead Agents — Coordinate and delegate work
    ↓
🤖 Task Agents — Execute specific assignments
```

**Head of Council**  
- Ultimate decision-maker with full system access
- Approves/rejects task proposals
- Manages system configuration

**Council Members**  
- Vote on important tasks and decisions
- Partial system access with oversight powers
- Auto-scale: 1 new member per 10 tasks

**Lead Agents**  
- Coordinate task distribution
- Manage agent teams
- Monitor execution progress

**Task Agents**  
- Execute assigned work
- Restricted permissions for security
- Auto-spawn based on workload

### Comprehensive Features

**🌐 Multi-Channel Integration**  
Connect via WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage, Microsoft Teams, and more.

**🎙️ Voice Interaction**  
Always-on speech recognition for macOS, iOS, and Android.

**🎨 Visual Workspace**  
Live canvas with agent-driven visual collaboration and A2UI support.

**🔧 Powerful Automation**  
- Browser control and automation
- Cron-scheduled tasks
- Webhook integrations
- Gmail Pub/Sub integration

**🔒 Enterprise Security**  
- Granular per-agent permissions
- Container sandboxing
- Complete audit logging
- Session management and pruning

**📊 Full Observability**  
- Real-time task monitoring
- Health checks and logging
- Performance metrics
- Audit trail for all actions

---

## 🏗️ Architecture

Agentium uses a containerized microservices architecture where each component runs in isolation:

```
┌─────────────────────────────────────────────┐
│  Web Dashboard (React + TypeScript)         │
│  Accessible from any browser/device         │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  API Gateway (FastAPI)                      │
│  WebSocket + REST endpoints                 │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Head of Council (AI Model)                 │
│  Full access • Decision authority           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Council Members (AI Models)                │
│  Voting • Partial access                    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Lead Agents (AI Models)                    │
│  Task coordination • Team management        │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Task Agents (AI Models)                    │
│  Execution • Restricted access              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Database (SQLite/PostgreSQL/VectorDB)      │
│  Audit logs • Session data • Configurations │
└─────────────────────────────────────────────┘
```

---
## Internal Documentation

### Constitution
- Begins with a standardized base template.
- Defines the **sovereign preferences** of the system.
- Specifies clear rules on permitted and prohibited actions.
- Updated through voting by Council Members and approved by the Head of Council.
- Constitution should be reviewed and updated daily.
- Read-only for all entities except the Head of Council.

---

### Individual Agent Ethos
- Every Agent possesses its own Ethos.
- The Ethos is created by the Agent’s immediate higher authority using a default template.
- Defines rules governing what the Agent **should** and **should not** do.
- May be updated by the Individual Agent, but must be reviewed and approved by the Lead Agent.
- For Lead Agents, the Ethos is reviewed and updated by the Head of Council.
- Agents may ask questions to their direct leader when clarification is needed.
- Ethos should be reviewed and updated daily.

---

### On Creation
- Each Head of Council, Council Member, Lead Agent, and Task Agent is created with a default Ethos.
- The Ethos is generated by the Agent’s higher authority using a default template.
- Upon creation, each entity must:
  - Read and acknowledge the Constitution.
  - Read and acknowledge its own Ethos.

---

### Termination
- The Head of Council is never terminated.
- A Council Member is terminated if it violates the Constitution.
- A Lead Agent is terminated if it violates the Constitution.
- A Task Agent is terminated if it violates the Constitution.
- Agents are terminated after completing their assigned tasks.
- Agents are terminated if inactive for more than one week.

---

### Identification
- All Agents are assigned a unique identification number.
- Identifier format:
  - **Head of Council:** `0xxxx`
  - **Council Member:** `1xxxx`
  - **Lead Agent:** `2xxxx`
  - **Task Agent:** `3xxxx`

---

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- 4GB+ RAM recommended
- Windows, macOS, or Linux

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/agentium.git
cd agentium

# Start the system
docker-compose up --build

# Access the dashboard
# Open http://localhost:3000 in your browser
# Default login: admin / admin
```

That's it! Your AI governance system is now running.

---

## 📖 Usage Guide

### Getting Started

1. **Login to Dashboard**  
   Navigate to `http://localhost:3000` and use the default credentials

2. **Configure API Keys**  
   Add your API keys for external AI services (optional)

3. **Send Your First Task**  
   Message the Head of Council through the chat interface

4. **Watch Democracy in Action**  
   - Head of Council receives your request
   - Council Members deliberate and vote
   - Lead Agents assign work
   - Task Agents execute
   - Results flow back to you

### Scaling:
  - System auto-scales based on load
  - Starts with Head of Council and two Council Members
  - Scales Lead Agents and Task Agents based on load
  - Lead Agents can also spawn LeadAgents if the number of TaskAgents exceeds a threshold eg, 50
  - If task is completed and  conform by the higher body the agent should be terminated
  - Maximum lifetime of an agent is 30 days.
  - If an agent is inactive for more than 7 days it should be terminated.
  - If an agent is terminated it should be removed from the system.

### Operations:
- Head of Council communicates with The Sovereign. and recives and distributes tasks to Council Members.
- Council Members assigns the task to lead Agents.  
- Lead Agents assign work to Task Agents.
- Task Agents execute tasks.
- Results flow back to Head of Council.
- Head of Council communicates with The Sovereign. and recives and distributes tasks to Council Members.  
- Voting is done when the task access is requested to Concil Members.
- Voting is done when adding, updating the constitution and planning for any new implementation to the system improvements.
- If their are no task given by the Sovereign then the Head of Council should ask the Council Members to vote on the task.
- The tasks should be focus on improving the Nation i.e The system, managing resources making the system efficent. 
- The Agents should never be ideal, The Head of Council and Concil Members should always be working and other agents should be terminated if ideal and no work. 


### Managing Your System

**Update Models**  
Switch between local and API models per role in `config/roles.json`

**Adjust Permissions**  
Control what each tier can access via the dashboard

**Monitor Activity**  
View real-time task status, votes, and execution logs

**Scale Resources**  
System auto-scales, but you can manually adjust limits

### Advanced Features

**Voice Commands**  
Enable always-on voice interaction for hands-free operation

**Browser Automation**  
Let agents interact with websites on your behalf

**Scheduled Tasks**  
Set up recurring jobs with cron syntax

**Multi-Channel**  
Connect messaging platforms for ubiquitous access

---

## ⚙️ Configuration

### Model Configuration

Edit `config/roles.json` to specify models for each role:

```json
{
  "head_of_council": {
    "model": "gpt-4",
    "type": "api"
  },
  "council_members": {
    "model": "kimi-2.5",
    "type": "local"
  }
}
```

### Permissions

Fine-grained access control per role:
- **Full Access**: Head of Council (all permissions) (Full System Scope)
- **Partial Access**: Council Members, (Partial permissions) (Partial System Scope)
- **Partial Access**: Lead Agents (partial permissions) (Partial System Scope) (can only access inside the scope of their assigned task)
- **Restricted Access**: Task Agents (restricted permissions) (Restricted System Scope) (can only access inside the scope of their assigned task)

- **Access Giving Authority**: Access can be given within the scope of the individual agent's access.
- **Access Revoking Authority**: Access can be revoked within the scope of the individual agent's access.
- **Access Modifying Authority**: Access can be modified within the scope of the individual agent's access.
- **Process**: - Head of council can give access of anything to anyone witin the system.
                - Concil Members can give access within their partial system scope.
                - Lead Agents can give access within their partial system scope.
                - Task Agents can give access within their restricted system scope. 
                - Head of council can revoke access of anything to anyone witin the system.
                - Concil Members can revoke access within their partial system scope.
                - Lead Agents can revoke access within their partial system scope.
                - Task Agents can revoke access within their restricted system scope. 
                - Head of council can modify access of anything to anyone witin the system.
                - Concil Members can modify access within their partial system scope.
                - Lead Agents can modify access within their partial system scope.
                - Task Agents can modify access within their restricted system scope. 

Update permissions dynamically through the dashboard.

### Messaging Channels

Configure integrations in `config/channels.json`:
- WhatsApp, Telegram, Slack
- Discord, Google Chat, Signal
- iMessage, Microsoft Teams
- Custom WebChat

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React, TypeScript |
| **Backend** | Python, FastAPI |
| **AI Models** | Local (Kimi 2.5, GPT-4) + API (Anthropic, OpenAI, Gemini) |
| **Database** | SQLite / PostgreSQL |
| **Containers** | Docker, docker-compose |
| **Communication** | WebSocket, REST API |
| **Deployment** | Local-first, Tailscale/SSH remote access |

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

- 🐛 Report bugs via GitHub Issues
- 💡 Suggest features and improvements
- 🔧 Submit pull requests
- 📖 Improve documentation
- 🌍 Add translations

Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting PRs.

---

## 📋 Roadmap

- [-] Project Development Ongoing
- [ ] Plugin marketplace for custom agents
- [ ] Mobile companion apps (iOS/Android)
- [ ] Advanced analytics dashboard
- [ ] Multi-user support with RBAC
- [ ] Integration with more AI providers
- [ ] Natural language config management

---

## 📄 License

This project is licensed - see the [LICENSE](LICENSE) file for details.

---



## 💬 Support

- 📚 [Documentation] (Coming Soon)
- 📧 Email: [EMAIL_ADDRESS]

---

<p align="center">
  <strong>Built with ❤️ and purpose by Ashmin Dhungana</strong>
</p>
