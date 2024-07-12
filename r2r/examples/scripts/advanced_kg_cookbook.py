import os
import string

import fire
import requests
from bs4 import BeautifulSoup, Comment

from r2r import (
    Document,
    EntityType,
    KGSearchSettings,
    R2RBuilder,
    R2RClient,
    R2RPromptProvider,
    Relation,
    VectorSearchSettings,
    generate_id_from_label,
)
from r2r.base.abstractions.llm import GenerationConfig


def escape_braces(text):
    return text.replace("{", "{{").replace("}", "}}")


def get_all_yc_co_directory_urls():
    this_file_path = os.path.abspath(os.path.dirname(__file__))
    yc_company_dump_path = os.path.join(
        this_file_path, "..", "data", "yc_companies.txt"
    )

    with open(yc_company_dump_path, "r") as f:
        urls = f.readlines()
    urls = [url.strip() for url in urls]
    return {url.split("/")[-1]: url for url in urls}


# Function to fetch and clean HTML content
def fetch_and_clean_yc_co_data(url):
    # Fetch the HTML content from the URL
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for bad status codes
    html_content = response.text

    # Parse the HTML content with BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove all <script>, <style>, <meta>, <link>, <header>, <nav>, and <footer> elements
    for element in soup(
        ["script", "style", "meta", "link", "header", "nav", "footer"]
    ):
        element.decompose()

    # Remove comments
    for comment in soup.findAll(text=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Select the main content (you can adjust the selector based on the structure of your target pages)
    main_content = soup.select_one("main") or soup.body

    if main_content:
        spans = main_content.find_all(["span", "a"])

        proc_spans = []
        for span in spans:
            proc_spans.append(span.get_text(separator=" ", strip=True))
        span_text = "\n".join(proc_spans)

        # Extract the text content from the main content
        paragraphs = main_content.find_all(
            ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]
        )
        cleaned_text = (
            "### Bulk:\n\n"
            + "\n\n".join(
                paragraph.get_text(separator=" ", strip=True)
                for paragraph in paragraphs
            )
            + "\n\n### Metadata:\n\n"
            + span_text
        )

        return cleaned_text
    else:
        return "Main content not found"


def execute_query(provider, query, params={}):
    print(f"Executing query: {query}")
    with provider.client.session(database=provider._database) as session:
        result = session.run(query, params)
        return [record.data() for record in result]


def main(
    max_entries=50,
    local_mode=True,
    base_url="http://localhost:8000",
):

    # Specify the entity types for the KG extraction prompt
    entity_types = [
        EntityType("ORGANIZATION"),
        EntityType("COMPANY"),
        EntityType("SCHOOL"),
        EntityType("NON-PROFIT"),
        EntityType("LOCATION"),
        EntityType("CITY"),
        EntityType("STATE"),
        EntityType("COUNTRY"),
        EntityType("PERSON"),
        EntityType("POSITION"),
        EntityType("DATE"),
        EntityType("YEAR"),
        EntityType("MONTH"),
        EntityType("DAY"),
        EntityType("BATCH"),
        EntityType("OTHER"),
        EntityType("QUANTITY"),
        EntityType("EVENT"),
        EntityType("INCORPORATION"),
        EntityType("FUNDING_ROUND"),
        EntityType("ACQUISITION"),
        EntityType("LAUNCH"),
        EntityType("INDUSTRY"),
        EntityType("MEDIA"),
        EntityType("EMAIL"),
        EntityType("WEBSITE"),
        EntityType("TWITTER"),
        EntityType("LINKEDIN"),
        EntityType("OTHER"),
        EntityType("PRODUCT"),
    ]

    # Specify the relations for the KG construction
    relations = [
        # Founder Relations
        Relation("EDUCATED_AT"),
        Relation("WORKED_AT"),
        Relation("FOUNDED"),
        # Company relations
        Relation("RAISED"),
        Relation("REVENUE"),
        Relation("TEAM_SIZE"),
        Relation("LOCATION"),
        Relation("ACQUIRED_BY"),
        Relation("ANNOUNCED"),
        Relation("INDUSTRY"),
        # Product relations
        Relation("PRODUCT"),
        Relation("FEATURES"),
        Relation("USES"),
        Relation("USED_BY"),
        Relation("TECHNOLOGY"),
        # Additional relations
        Relation("HAS"),
        Relation("AS_OF"),
        Relation("PARTICIPATED"),
        Relation("ASSOCIATED"),
        Relation("GROUP_PARTNER"),
        Relation("ALIAS"),
    ]

    client = R2RClient(base_url=base_url)
    r2r_prompts = R2RPromptProvider()

    # get the default extraction template
    # note that 'local' templates omit the n-shot example
    new_template = r2r_prompts.get_prompt(
        (
            "zero_shot_ner_kg_extraction_with_spec"
            if local_mode
            else "few_shot_ner_kg_extraction_with_spec"
        ),
        {
            "entity_types": "\n".join(
                [str(entity.name) for entity in entity_types]
            ),
            "relations": "\n".join(
                [str(relation.name) for relation in relations]
            ),
            "input": """\n{input}""",
        },
    )

    # Escape all braces in the template, except for the {input} placeholder, for formatting
    escaped_template = escape_braces(new_template).replace(
        """{{input}}""", """{input}"""
    )

    client.update_prompt(
        (
            "zero_shot_ner_kg_extraction"
            if local_mode
            else "few_shot_ner_kg_extraction"
        ),
        template=escaped_template,
        input_types={"input": "str"},
    )

    url_map = get_all_yc_co_directory_urls()

    i = 0
    # Ingest and clean the data for each company
    for company, url in url_map.items():
        company_data = fetch_and_clean_yc_co_data(url)
        if i >= max_entries:
            break
        i += 1

        try:
            # Ingest as a text document
            file_name = f"{company}.txt"
            with open(file_name, "w") as f:
                f.write(company_data)

            client.ingest_files(
                [file_name],
                metadatas=[{"title": company}],
            )
            os.remove(file_name)
        except:
            continue

    print(client.inspect_knowledge_graph(1_000)["results"])

    new_template = r2r_prompts.get_prompt(
        "kg_agent_with_spec",
        {
            "entity_types": "\n".join(
                [str(entity.name) for entity in entity_types]
            ),
            "relations": "\n".join(
                [str(relation.name) for relation in relations]
            ),
            "input": """\n{input}""",
        },
    )
    if not local_mode:
        # RAG client currently only works with powerful remote LLMs,
        # we are working to expand support to local LLMs.
        client.update_prompt(
            "kg_agent",
            template=new_template,
            input_types={"input": "str"},
        )

        result = client.search(
            query="Find up to 10 founders that worked at Google",
            use_kg_search=True,
        )["results"]

        print("result:\n", result)
        print("Search Result:\n", result["kg_search_results"])

        result = client.rag(
            query="Find up to 10 founders that worked at Google",
            use_kg_search=True,
        )
        print("RAG Result:\n", result)


if __name__ == "__main__":
    fire.Fire(main)
