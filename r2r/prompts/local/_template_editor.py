import json

prompt1 = """
### Instruction

You will shortly be asked to perform Named Entity Recognition (NER) and knowledge graph triplet extraction on the text that follows. NER involves identifying named entities in a text, and knowledge graph triplet extraction involves identifying relationships between these entities and other attributes in the text. Output a JSON. 

A knowledge graph triplet contains the three following pieces of information:

- `subject`: The main entity.
- `predicate`: The relationship type.
- `object`: The related entity.

They are represented below as `[subject]:<predicate>:[object]`.

#### Process 
**Identify Named Entities**: Extract entities based on the given entity types, ensuring they appear in the order they are mentioned in the text.

**Establish Triplets**: Form triplets using the provided predicates, again in the order they appear in the text.

Your final response should follow this format:


**Output:**
{{
  "entities_and_triples": [
    "[1], entity_type:entity_name",
    "[1] predicate [2]",
    "[1] predicate [3]",
    "[2], entity_type:entity_name"
  ]
}}

### Example:

**Entity Types:**
{{
    "entity_types": [
        "ORGANIZATION",
        "COMPANY",
        "CITY",
        "STATE",
        "COUNTRY",
        "OTHER",
        "PERSON",
        "YEAR",
        "MONTH",
        "DAY",
        "OTHER",
        "QUANTITY",
        "EVENT"
    ]
}}

**Predicates:**
{{
  "predicates": [
    "FOUNDED_BY",
    "HEADQUARTERED_IN",
    "OPERATES_IN",
    "OWNED_BY",
    "ACQUIRED_BY",
    "HAS_EMPLOYEE_COUNT",
    "GENERATED_REVENUE",
    "LISTED_ON",
    "INCORPORATED",
    "HAS_DIVISION",
    "ALIAS",
    "ANNOUNCED",
    "HAS_QUANTITY",
    "AS_OF"
  ]
}}


**Text:**
Walmart Inc. (formerly Wal-Mart Stores, Inc.) is an American multinational retail corporation that operates a chain of hypermarkets (also called supercenters), discount department stores, and grocery stores in the United States, headquartered in Bentonville, Arkansas.[10] The company was founded by brothers Sam and James \"Bud\" Walton in nearby Rogers, Arkansas in 1962 and incorporated under Delaware General Corporation Law on October 31, 1969. It also owns and operates Sam's Club retail warehouses.[11][12]

As of October 31, 2022, Walmart has 10,586 stores and clubs in 24 countries, operating under 46 different names.[2][3][4] The company operates under the name Walmart in the United States and Canada, as Walmart de M\u00e9xico y Centroam\u00e9rica in Mexico and Central America, and as Flipkart Wholesale in India.

**Output:**
{{
  "entities_and_triples": [
    "[1], COMPANY:Walmart Inc.",
    "[2], company:Wal-Mart Stores, Inc.",
    "[1] ALIAS [2]",
    "[3], COUNTRY:United States",
    "[1] OPERATES_IN [3]",
    "[4], CITY:Bentonville",
    "[1] HEADQUARTERED_IN [4]",
    "[5], STATE:Arkansas",
    "[1] HEADQUARTERED_IN [5]",
    "[6], PERSON:Sam Walton",
    "[1] FOUNDED_BY [6]",
    "[7], PERSON:James Walton",
    "[8], PERSON:Bud Walton",
    "[7] ALIAS [8]",
    "[1] FOUNDED_BY [7]",
    "[9], CITY:Rogers",
    "[10], YEAR:1962",
    "[11], EVENT:incorporated under Delaware General Corporation Law",
    "[1] INCORPORATED [11]",
    "[12], DAY:October 31",
    "[1] INCORPORATED [12]",
    "[13], YEAR:1969",
    "[1] INCORPORATED [13]",
    "[14], COMPANY:Sam's Club",
    "[1] INCORPORATED [14]",
    "[15], DAY:October 31, 2022",
    "[16], QUANTITY:10,586 stores and clubs",
    "[16] AS_OF [15]",
    "[1] HAS_QUANTITY [16]",
    "[17], QUANTITY:24 countries",
    "[18], QUANTITY:46 different names",
    "[1] HAS_QUANTITY [18]",
    "[18], ORGANIZATION:company:Walmart de México y Centroamérica",
    "[1] ALIAS [18]",
    "[19], LOCATION:country:Mexico",
    "[1] OPERATES_IN [19]",
    "[20], organization:company:Flipkart Wholesale",
    "[1] ALIAS [20]",
    "[21], location:country:India",
    "[1] OPERATES_IN [21]"
  ]
}}

### Task:\nYour task is to perform Named Entity Recognition (NER) and knowledge graph triplet extraction on the text that follows below.\n\n**Input:**\n{input}\n\n**

ENTITY_PREDICATE_SPEC
**Input:**
{input}

**Output:**

"""

ENTITY_PREDICATE_SPEC = """
***Entity Types:***
{entity_types}

***Predicates:***
{predicates}
"""


json_arr = []
json_str = {'name': 'few_shot_ner_kg_extraction', 'template': prompt1.replace("ENTITY_PREDICATE_SPEC", ''), "input_types": {"input": "str"}}
json_arr.append(json_str)

json_str = {'name': 'few_shot_ner_kg_extraction_with_spec', "template": prompt1.replace("ENTITY_PREDICATE_SPEC", ENTITY_PREDICATE_SPEC), "input_types": {"input": "str", "entity_types": "str", "predicates": "str"}}
json_arr.append(json_str)



prompt2 = """
Perform Named Entity Recognition (NER) and extract knowledge graph triplets from the text. NER identifies named entities of given entity types, and triple extraction identifies relationships between entities using specified predicates.

**Entity Types**
{entity_types}

**Predicates**
{predicates}

**Input**
{input}
"""


DEFAULT_ENTITY_TYPES = 'PERSON, LOCATION, HOUSE, TITLE, ORGANIZATION, EVENT, CREATURE, WEAPON, POSITION, ARMY'.split(', ')
DEFAULT_ENTITY_TYPES = "{" + json.dumps({'entity_types': DEFAULT_ENTITY_TYPES}, indent=4) + "}"

DEFAULT_PREDICATES = "MEMBER_OF, PARENT_OF, CHILD_OF, SIBLING_OF, SPOUSE_OF, RULER_OF, SERVES_AS, LOYAL_TO, ADVISOR_TO, GUARDIAN_OF, ALLIED_WITH, ENEMY_OF, KILLED_BY, EXILED_BY, FOSTERED_BY, BETROTHED_TO, KIDNAPPED_BY, SUCCEEDED_BY, PREDECESSOR_OF, LOCATED_IN, WIELDS, FOUNDER_OF, HEIR_TO, COMMANDER_OF".split(', ')
DEFAULT_PREDICATES = "{" + json.dumps({'predicates': DEFAULT_PREDICATES}, indent=4) + "}"


json_str = {'name': 'zero_shot_ner_kg_extraction', 'template': prompt2.replace("entity_types", DEFAULT_ENTITY_TYPES).replace("predicates", DEFAULT_PREDICATES), "input_types": {"input": "str"}}
json_arr.append(json_str)

json_str = {'name': 'zero_shot_ner_kg_extraction_with_spec', 'template': prompt2, "input_types": {"input": "str", "entity_types": "str", "predicates": "str"}}
json_arr.append(json_str)

# save each line in json arral
with open('template.jsonl', 'w') as f:
    for item in json_arr:
        f.write(json.dumps(item) + '\n')

arr = []
with open('template.jsonl', 'r') as f:
    for line in f:
        arr.append(json.loads(line))
