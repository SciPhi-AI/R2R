from typing import Any, Dict

from r2r.core import AgentProvider, LLMProvider, PromptProvider


class DefaultAgentProvider(AgentProvider):
    def __init__(
        self, llm_provider: LLMProvider, prompt_provider: PromptProvider
    ):
        super().__init__(llm_provider, prompt_provider)

    def create_agent(self, agent_name: str, agent_config: dict) -> None:
        if agent_name in self.agents:
            raise ValueError(f"Agent '{agent_name}' already exists.")
        # Create the agent based on the agent_config and add it to the agents dictionary
        agent = self._create_agent_instance(agent_config)
        self.agents[agent_name] = agent

    def get_agent(self, agent_name: str) -> Any:
        agent = self.agents.get(agent_name)
        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not found.")
        return agent

    def remove_agent(self, agent_name: str) -> None:
        if agent_name not in self.agents:
            raise ValueError(f"Agent '{agent_name}' not found.")
        del self.agents[agent_name]

    def get_all_agents(self) -> Dict[str, Any]:
        return self.agents.copy()

    def _create_agent_instance(self, agent_config: dict) -> Any:
        # Implement the logic to create an agent instance based on the agent_config
        # This could involve using the llm_provider and prompt_provider to instantiate the agent
        pass
