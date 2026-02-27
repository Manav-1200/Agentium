# Project Structure Documentation

This document provides a comprehensive overview of the Agentium project directory structure.

```
Agentium/
├── .github/                          # GitHub configuration
│   └── workflows/
│       └── docker-image.yml          # CI/CD Docker image workflow
├── bridges/                          # External service integrations
│   └── whatsapp/                    # WhatsApp bridge integration
│       ├── Dockerfile                # WhatsApp bridge container
│       ├── package.json              # Node.js dependencies
│       └── package-lock.json
├── backend/                          # Python FastAPI backend
│   ├── alembic/                      # Database migrations
│   │   ├── env.py                   # Alembic environment config
│   │   └── versions/                # Migration scripts
│   │       ├── 001_schema.py        # Initial schema
│   │       ├── 002_mcp_tools.py     # MCP tools migration
│   │       ├── 003_user_preferences.py # User preferences migration
│   │       └── 002_ab_testing.py    # A/B testing migration
│   ├── api/                          # API layer
│   │   ├── dependencies/
│   │   │   └── auth.py              # Auth dependencies
│   │   ├── middleware/
│   │   │   └── auth.py               # Auth middleware
│   │   ├── routes/                  # API endpoints
│   │   │   ├── admin.py             # Admin endpoints
│   │   │   ├── api_keys.py          # API key management
│   │   │   ├── auth.py              # Authentication
│   │   │   ├── user_preferences.py  # User preferences
│   │   │   ├── capability_routes.py # Capabilities API
│   │   │   ├── channels.py          # Channel management
│   │   │   ├── chat.py              # Chat endpoints
│   │   │   ├── checkpoints.py       # Checkpoint management
│   │   │   ├── critics.py           # Critic agents
│   │   │   ├── files.py             # File operations
│   │   │   ├── inbox.py             # Unified inbox
│   │   │   ├── lifecycle_routes.py  # Lifecycle management
│   │   │   ├── mcp_tools.py         # MCP tools
│   │   │   ├── models.py            # Model management
│   │   │   ├── monitoring_routes.py # Monitoring endpoints
│   │   │   ├── remote_executor.py   # Remote execution
│   │   │   ├── tasks.py             # Task management
│   │   │   ├── tool_creation.py     # Tool creation
│   │   │   ├── tools.py             # Tool registry
│   │   │   ├── user_preferences.py  # User preferences
│   │   │   ├── voice.py             # Voice features
│   │   │   ├── voting.py            # Voting/constitution
│   │   │   ├── webhooks.py          # Webhook handlers
│   │   │   ├── websocket.py         # WebSocket endpoints
│   │   │   ├── ab_testing.py        # A/B testing
│   │   │   └── provider_analytics.py # Provider analytics
│   │   ├── schemas/                 # Pydantic schemas
│   │   │   ├── checkpoint.py
│   │   │   ├── mcp_schemas.py
│   │   │   ├── user_preference.py
│   │   │   ├── remote_executor.py
│   │   │   ├── task.py
│   │   │   └── tool_creation.py
│   │   ├── host_access.py           # Host access API
│   │   └── sovereign.py             # Sovereign governance API
│   ├── core/                        # Core functionality
│   │   ├── auth.py                  # Authentication logic
│   │   ├── config.py                # Configuration
│   │   ├── constitutional_guard.py  # Constitutional governance
│   │   ├── security/                # Security module
│   │   │   ├── __init__.py
│   │   │   └── execution_guard.py   # Execution safety
│   │   ├── tool_registry.py         # Tool registry
│   │   └── vector_store.py          # Vector embeddings
│   ├── models/                      # Database models
│   │   ├── database.py              # Database setup
│   │   ├── entities/                # SQLAlchemy entities
│   │   │   ├── __init__.py
│   │   │   ├── agents.py             # Agent definitions
│   │   │   ├── audit.py              # Audit logs
│   │   │   ├── base.py               # Base entity
│   │   │   ├── channels.py           # Channel configs
│   │   │   ├── chat_message.py       # Chat messages
│   │   │   ├── checkpoint.py         # Execution checkpoints
│   │   │   ├── constitution.py       # Constitution rules
│   │   │   ├── critics.py            # Critic agents
│   │   │   ├── mcp_tool.py            # MCP tools
│   │   │   ├── model_provider.py     # LLM providers
│   │   │   ├── monitoring.py         # Monitoring data
│   │   │   ├── remote_execution.py   # Remote execution
│   │   │   ├── scheduled_task.py     # Scheduled tasks
│   │   │   ├── system_settings.py    # System config
│   │   │   ├── task_events.py        # Task events
│   │   │   ├── task.py               # Task definitions
│   │   │   ├── tool_marketplace_listing.py # Marketplace
│   │   │   ├── tool_staging.py       # Tool staging
│   │   │   ├── tool_usage_log.py     # Usage logs
│   │   │   ├── tool_version.py        # Tool versioning
│   │   │   ├── user_config.py         # User preferences
│   │   │   ├── user.py                # User entities
│   │   │   ├── user_preference.py     # User preferences
│   │   │   ├── voting.py              # Voting records
│   │   │   └── ab_testing.py          # A/B testing
│   │   └── schemas/                   # Request/response schemas
│   │       ├── messages.py
│   │       ├── task.py
│   │       └── tool_creation.py
│   ├── scripts/                      # Utility scripts
│   │   ├── __init__.py
│   │   ├── create_initial_admin.py   # Admin setup
│   │   ├── init_db.py                 # Database init
│   │   ├── init_vector_db.py          # Vector DB init
│   │   └── verify_channels.py         # Channel verification
│   ├── services/                     # Business logic services
│   │   ├── acceptance_criteria.py     # Task validation
│   │   ├── agent_orchestrator.py      # Agent management
│   │   ├── amendment_service.py       # Constitution amendments
│   │   ├── api_key_manager.py         # API key handling
│   │   ├── api_manager.py             # API management
│   │   ├── user_preference_service.py # User preferences
│   │   ├── audit/                     # Audit logging
│   │   │   ├── __init__.py
│   │   │   └── audit_processor.py
│   │   ├── idle_tasks/
│   │   │   └── preference_optimizer.py
│   │   ├── auth.py                    # Authentication service
│   │   ├── capability_registry.py    # Agent capabilities
│   │   ├── channel_manager.py         # Channel orchestration
│   │   ├── channels/                  # Channel integrations
│   │   │   ├── base.py                 # Base channel
│   │   │   ├── slack.py               # Slack integration
│   │   │   └── whatsapp_unified.py   # WhatsApp integration
│   │   ├── chat_service.py            # Chat handling
│   │   ├── checkpoint_service.py      # Checkpoint management
│   │   ├── clarification_service.py   # Clarification requests
│   │   ├── context_manager.py         # Context handling
│   │   ├── critic_agents.py          # Critic agent logic
│   │   ├── host_access.py            # Host access service
│   │   ├── idle_governance.py        # Idle management
│   │   ├── initialization_service.py  # System init
│   │   ├── knowledge_governance.py    # Knowledge policies
│   │   ├── knowledge_service.py      # Knowledge base
│   │   ├── mcp_client.py             # MCP client
│   │   ├── mcp_governance.py         # MCP governance
│   │   ├── mcp_tool_bridge.py       # MCP tool bridge
│   │   ├── message_bus.py           # Message bus
│   │   ├── model_allocation.py       # Model allocation
│   │   ├── model_provider.py         # LLM provider mgmt
│   │   ├── monitoring/               # Monitoring services
│   │   │   ├── __init__.py
│   │   │   └── health_checks.py
│   │   ├── monitoring_service.py     # System monitoring
│   │   ├── persistent_council.py     # Persistent council
│   │   ├── prompt_template_manager.py # Prompt templates
│   │   ├── reincarnation_service.py   # Agent reincarnation
│   │   ├── remote_executor/          # Remote execution
│   │   │   ├── __init__.py
│   │   │   ├── executor.py
│   │   │   ├── sandbox.py
│   │   │   └── service.py
│   │   ├── task_state_machine.py    # Task state logic
│   │   ├── tasks/                   # Task execution
│   │   │   ├── __init__.py
│   │   │   └── task_executor.py
│   │   ├── token_optimizer.py       # Token optimization
│   │   ├── tool_analytics.py        # Tool analytics
│   │   ├── tool_creation_service.py  # Tool creation
│   │   ├── tool_deprecation.py      # Tool deprecation
│   │   ├── tool_factory.py           # Tool factory
│   │   ├── tool_marketplace.py       # Tool marketplace
│   │   ├── tool_versioning.py       # Tool versioning
│   │   └── ab_testing_service.py     # A/B testing service
│   ├── tools/                       # Built-in tools
│   │   ├── browser_tool.py          # Browser automation
│   │   ├── user_preference_tool.py  # User preference operations
│   │   ├── desktop_tool.py          # Desktop operations
│   │   ├── file_tool.py             # File operations
│   │   ├── host_os_tool.py          # Host OS access
│   │   └── shell_tool.py            # Shell commands
│   ├── tests/                       # Backend tests
│   │   ├── services/
│   │   │   └── test_capability_registry.py
│   │   ├── test_remote_executor.py
│   │   └── test_voting.py
│   ├── alembic.ini                  # Alembic config
│   ├── celery_app.py               # Celery async tasks
│   ├── Dockerfile                   # Backend container
│   ├── Dockerfile.privileged       # Privileged container
│   ├── Dockerfile.remote-executor   # Remote executor
│   ├── main.py                      # FastAPI app entry
│   └── requirements.txt            # Python dependencies
│
├── frontend/                        # React TypeScript frontend
│   ├── public/                     # Static assets
│   ├── src/
│   │   ├── components/             # React components
│   │   │   ├── agents/             # Agent components
│   │   │   │   ├── AgentCard.tsx
│   │   │   │   ├── AgentTree.tsx
│   │   │   │   └── SpawnAgentModal.tsx
│   │   │   ├── checkpoints/         # Checkpoint UI
│   │   │   │   ├── CheckpointTimeline.tsx
│   │   │   │   └── BranchDiffView.tsx
│   │   │   ├── channels/             # Channel UI
│   │   │   │   ├── ChannelMetricsCard.tsx
│   │   │   │   ├── CircuitBreakerBadge.tsx
│   │   │   │   └── MessageLogViewer.tsx
│   │   │   ├── common/             # Shared components
│   │   │   │   ├── ErrorBoundary.tsx
│   │   │   │   └── ProtectedRoute.tsx
│   │   │   ├── council/            # Governance UI
│   │   │   │   └── VotingInterface.tsx
│   │   │   ├── dashboard/          # Dashboard components
│   │   │   │   ├── ChannelHealthWidget.tsx
│   │   │   │   ├── FinancialBurnDashboard.tsx
│   │   │   │   └── ProviderAnalytics.tsx
│   │   │   ├── layout/             # Layout components
│   │   │   │   └── MainLayout.tsx
│   │   │   ├── models/             # Model config UI
│   │   │   │   └── ModelConfigForm.tsx
│   │   │   ├── mcp/               # MCP tools UI
│   │   │   │   └── MCPToolRegistry.tsx
│   │   │   ├── monitoring/         # Monitoring UI
│   │   │   │   ├── APIKeyHealth.tsx
│   │   │   │   ├── HealthScore.tsx
│   │   │   │   └── ViolationCard.tsx
│   │   │   ├── tasks/              # Task UI
│   │   │   │   ├── CreateTaskModal.tsx
│   │   │   │   └── TaskCard.tsx
│   │   │   ├── BudgetControl.tsx
│   │   │   ├── ConnectionStatus.tsx
│   │   │   ├── FlatMapAuthBackground.tsx
│   │   │   ├── GlobalWebSocketProvider.tsx
│   │   │   ├── HealthIndicator.tsx
│   │   │   ├── SovereignRoute.tsx
│   │   │   └── UnifiedInbox.tsx
│   │   ├── hooks/                   # Custom React hooks
│   │   │   └── useWebSocket.ts
│   │   ├── pages/                   # Page components
│   │   │   ├── AgentsPage.tsx
│   │   │   ├── ChannelsPage.tsx
│   │   │   ├── ChatPage.tsx
│   │   │   ├── ConstitutionPage.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── LoginPage.tsx
│   │   │   ├── ModelsPage.tsx
│   │   │   ├── MonitoringPage.tsx
│   │   │   ├── SettingsPage.tsx
│   │   │   ├── SignupPage.tsx
│   │   │   ├── SovereignDashboard.tsx
│   │   │   ├── TasksPage.tsx
│   │   │   ├── Usermanagement.tsx
│   │   │   ├── VotingPage.tsx
│   │   │   ├── ABTestingPage.tsx
│   │   │   └── MessageLogPage.tsx
│   │   ├── services/                # API service layers
│   │   │   ├── abTesting.ts
│   │   │   ├── admin.ts
│   │   │   ├── agents.ts
│   │   │   ├── api.ts
│   │   │   ├── auth.ts
│   │   │   ├── chatApi.ts
│   │   │   ├── channelMessages.ts
│   │   │   ├── channelMetrics.ts
│   │   │   ├── checkpoints.ts
│   │   │   ├── constitution.ts
│   │   │   ├── fileApi.ts
│   │   │   ├── hostAccessApi.ts
│   │   │   ├── inboxApi.ts
│   │   │   ├── localVoice.ts
│   │   │   ├── models.ts
│   │   │   ├── monitoring.ts
│   │   │   ├── preferences.ts
│   │   │   ├── tasks.ts
│   │   │   ├── voiceApi.ts
│   │   │   └── voting.ts
│   │   ├── store/                   # State management
│   │   │   ├── authStore.ts
│   │   │   ├── backendStore.ts
│   │   │   ├── chatStore.ts
│   │   │   └── websocketStore.ts
│   │   ├── types/                   # TypeScript types
│   │   │   ├── hostAccess.ts
│   │   │   └── index.ts
│   │   ├── App.tsx                  # Root component
│   │   ├── App.css                  # App styles
│   │   ├── index.css                # Global styles
│   │   └── main.tsx                  # Entry point
│   ├── Dockerfile
│   ├── eslint.config.js
│   ├── index.html
│   ├── nginx.conf
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.app.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── vite.config.ts
│
├── docs/                            # Documentation
│   ├── selfhost.md                  # Self-hosting guide
│   ├── todo.md                      # TODO list
│   ├── constitution/
│   │   └── core.md                  # Constitution core
│   ├── verification_1_7_phase.md    # Verification phase doc
│   └── workflow/                    # Workflow docs
│       ├── channel_verification.md
│       ├── dev_workflow.md
│       ├── multimodel_chat.md
│       ├── system_workflow.md
│       ├── task_execution.md
│       └── unified_inbox.md
├── .gitignore
├── .github/
│   └── workflows/
│       └── docker-image.yml
├── CONTRIBUTING.md                   # Contributing guidelines
├── LICENSE
├── README.md
├── docker-compose.yml               # Main compose file
├── docker-compose.remote-executor.yml
└── package.json                     # Root package (metadata)
```

## Architecture Overview

### Backend (Python/FastAPI)

- **api/**: REST API endpoints organized by feature
- **core/**: Core application logic (auth, config, security)
- **models/**: Database layer with SQLAlchemy entities
- **services/**: Business logic microservices
- **tools/**: Built-in agent tools

### Frontend (React/TypeScript)

- **components/**: Reusable UI components
- **pages/**: Route-level page components
- **services/**: API communication layer
- **store/**: State management (Zustand)
- **hooks/**: Custom React hooks

### Infrastructure

- **bridges/**: External service integrations (WhatsApp)
- **docker-compose.yml**: Container orchestration
