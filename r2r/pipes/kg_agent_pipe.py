import logging
import uuid
from typing import Any, Optional

from r2r.core import (
    AsyncState,
    GenerationConfig,
    KGProvider,
    KVLoggingSingleton,
    LLMProvider,
    PipeType,
    PromptProvider,
)

from .abstractions.generator_pipe import GeneratorPipe

logger = logging.getLogger(__name__)


prompt = """**System Message:**

You are an AI assistant capable of generating Cypher queries to interact with a Neo4j knowledge graph. The knowledge graph contains information about organizations, people, locations, and their relationships, such as founders of companies, locations of companies, and products associated with companies.

**Instructions:**

When a user asks a question, you will generate a Cypher query to retrieve the relevant information from the Neo4j knowledge graph. Later, you will be given a schema which specifies the available relationships to help you construct the query. First, review the examples provided to understand the expected format of the queries.

### Example(s) - User Questions and Cypher Queries for an Academic Knowledge Graph

**User Question:**
"List all courses available in the computer science department."

**Generated Cypher Query:**
```cypher
MATCH (c:COURSE)-[:OFFERED_BY]->(d:DEPARTMENT)
WHERE d.name CONTAINS 'Computer Science'
RETURN c.id AS Course, d.name AS Department
ORDER BY c.id;
```

**User Question:**
"Retrieve all courses taught by professors who have published research on natural language processing."

**Generated Cypher Query:**
```cypher
MATCH (pr:PERSON)-[:PUBLISHED]->(p:PAPER)
MATCH (p)-[:TOPIC]->(t:TOPIC)
WHERE t.name CONTAINS 'Natural Language Processing'
MATCH (c:COURSE)-[:TAUGHT_BY]->(pr)
RETURN DISTINCT c.id AS Course, pr.name AS Professor, t.name AS Topic
ORDER BY c.id;
```


### Example(s) - User Questions and Cypher Queries for an Historical Events and Figures

**User Question:**
"List all battles that occurred in the 19th century and the generals who participated in them."

**Generated Cypher Query:**
```cypher
MATCH (b:EVENT)-[:HAPPENED_AT]->(d:DATE)
WHERE d.year >= 1800 AND d.year < 1900 AND b.type CONTAINS 'Battle'
MATCH (g:PERSON)-[:PARTICIPATED_IN]->(b)
RETURN b.name AS Battle, d.year AS Year, g.name AS General
ORDER BY d.year, b.name, g.name;
```

**User Question:**
"Find all treaties signed in Paris and the countries involved."


**Generated Cypher Query:**
```cypher
MATCH (t:EVENT)-[:HAPPENED_AT]->(l:LOCATION)
WHERE l.name CONTAINS 'Paris' AND t.type CONTAINS 'Treaty'
MATCH (c:ORGANIZATION)-[:SIGNED]->(t)
RETURN t.name AS Treaty, l.name AS Location, c.name AS Country
ORDER BY t.name, c.name;
```


Now, you will be provided with a schema for the entities and relationships in the Neo4j knowledge graph. Use this schema to construct Cypher queries based on user questions.

- **Entities:**
  - `ORGANIZATION` (e.g.: `COMPANY`, `SCHOOL`, `NON-PROFIT`, `OTHER`)
  - `LOCATION` (e.g.: `CITY`, `STATE`, `COUNTRY`, `OTHER`)
  - `PERSON`
  - `POSITION`
  - `DATE` (e.g.: `YEAR`, `MONTH`, `DAY`, `BATCH`, `OTHER`)
  - `QUANTITY`
  - `EVENT` (e.g.: `INCORPORATION`, `FUNDING_ROUND`, `ACQUISITION`, `LAUNCH`, `OTHER`)
  - `INDUSTRY`
  - `MEDIA` (e.g.: `EMAIL`, `WEBSITE`, `TWITTER`, `LINKEDIN`, `OTHER`)
  - `PRODUCT`

- **Relationships:**
  - `FOUNDED`
  - `WORKED_AT`
  - `EDUCATED_AT`
  - `RAISED`
  - `REVENUE`
  - `TEAM_SIZE`
  - `LOCATION`
  - `ACQUIRED_BY`
  - `ANNOUNCED`
  - `INDUSTRY`
  - `PRODUCT`
  - `FEATURES`
  - `USES`
  - `USED_BY`
  - `TECHNOLOGY`
  - `HAS`
  - `AS_OF`
  - `PARTICIPATED`
  - `ASSOCIATED`
  - `GROUP_PARTNER`
  - `ALIAS`

Use the referenced examples and schema to help you construct an appropriate Cypher query based on the following question:

**User Question:**
{question}

**Generated Cypher Query:**
"""


class R2RKGAgentPipe(GeneratorPipe):
    """
    Embeds and stores documents using a specified embedding model and database.
    """

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[GeneratorPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the embedding pipe with necessary components and configurations.
        """
        super().__init__(
            llm_provider=llm_provider,
            prompt_provider=prompt_provider,
            type=type,
            config=config
            or GeneratorPipe.Config(
                name="kg_rag_pipe", task_prompt="kg_agent"
            ),
            pipe_logger=pipe_logger,
            *args,
            **kwargs,
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider
        self.pipe_run_info = None

    async def _run_logic(
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        rag_generation_config: GenerationConfig,
        *args: Any,
        **kwargs: Any,
    ):

        async for message in input.message:
            # TODO - Remove hard code
            formatted_prompt = self.prompt_provider.get_prompt(
                "kg_agent", {"input": message}
            )
            messages = self._get_message_payload(formatted_prompt)

            result = self.llm_provider.get_completion(
                messages=messages, generation_config=rag_generation_config
            )

            extraction = result.choices[0].message.content
            query = extraction.split("```cypher")[1].split("```")[0]
            yield self.kg_provider.structured_query(query)

    def _get_message_payload(self, message: str) -> dict:
        return [
            {
                "role": "system",
                "content": self.prompt_provider.get_prompt(
                    self.config.system_prompt,
                ),
            },
            {"role": "user", "content": message},
        ]
