checkpoint_service.py — export_checkpoint, validate_import_data, import_checkpoint are defined at module level with @staticmethod decorators outside the CheckpointService class. They won't be accessible as CheckpointService.export_checkpoint() — they're just bare module-level functions that also reference json and hashlib without importing them.

knowledge_governance.py — staged_submissions is an in-memory dict on the service instance. Since KnowledgeGovernanceService is instantiated per-request (not a singleton), pending submissions are lost between requests. Either needs to be a singleton or submissions need to be persisted to DB.

clarification_service.py — imported in agent_orchestrator.py but ClarificationService is never actually called anywhere in the orchestrator. It's dead import weight for now.

agent_orchestrator.py → execute_task() — accesses agent.preferred_config.provider and agent.preferred_config.default_model after db.refresh(agent) but preferred_config is a relationship that may not be loaded post-refresh depending on session config, which could cause a lazy-load or detached instance error.

prune_obsolete_content in constitution.py use llm to summuarize the ethos. currently uses python logic.
