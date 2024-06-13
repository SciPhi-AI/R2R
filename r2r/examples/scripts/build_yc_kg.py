import json
import os

import fire
import requests
from bs4 import BeautifulSoup, Comment

from r2r import Document, R2RAppBuilder, R2RConfig, generate_id_from_label


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


def delete_all_entries(provider):
    delete_query = "MATCH (n) DETACH DELETE n;"
    with provider.client.session(database=provider._database) as session:
        session.run(delete_query)
    print("All entries deleted.")


def print_all_relationships(provider):
    rel_query = """
    MATCH (n1)-[r]->(n2)
    RETURN n1.id AS subject, type(r) AS predicate, n2.id AS object;
    """
    with provider.client.session(database=provider._database) as session:
        results = session.run(rel_query)
        for record in results:
            print(
                f"{record['subject']} -[{record['predicate']}]-> {record['object']}"
            )


def main(max_entries=50, delete=False):
    # Load the R2R configuration and build the app
    this_file_path = os.path.abspath(os.path.dirname(__file__))
    config_path = os.path.join(
        this_file_path, "..", "configs", "neo4j_kg.json"
    )
    config = R2RConfig.from_json(config_path)
    r2r = R2RAppBuilder(config).build()

    # Get the providers
    kg_provider = r2r.providers.kg
    prompt_provider = r2r.providers.prompt

    # Update the prompt for the NER KG extraction task
    ner_kg_extraction_with_spec = prompt_provider.get_prompt(
        "ner_kg_extraction_with_spec"
    )

    # Newline separated list of entity types, with optional subcategories
    entity_types = """organization
subcategories: company, school, non-profit, other
location
subcategories: city, state, country, other
person
position
date
subcategories: year, month, day, batch (e.g. W24, S20), other
quantity
event
subcategories: incorporation, funding_round, acquisition, launch, other
industry
media
subcategories: email, website, twitter, linkedin, other
product
"""
    # Newline separated list of predicates
    predicates = """
# Founder / employee predicates
EDUCATED_AT
FOUNDED
ROLE_OF
WORKED_AT
# Company predicates
FOUNDED_IN
LOCATED_IN
HAS_TEAM_SIZE
REVENUE
RAISED
ACQUIRED_BY
ANNOUNCED
PARTICIPATED_IN
# Product predicates
USED_BY
USES
HAS_PRODUCT
HAS_FEATURES
HAS_OFFERS
# Other
INDUSTRY
TECHNOLOGY
GROUP_PARTNER
ALIAS
HAS
CONTAINS
"""

    # Format the prompt to include the desired entity types and predicates
    ner_kg_extraction = ner_kg_extraction_with_spec.replace(
        "{entity_types}", entity_types
    ).replace("{predicates}", predicates)

    # Update the "ner_kg_extraction" prompt used in downstream pipes
    r2r.providers.prompt.update_prompt(
        "ner_kg_extraction", json.dumps(ner_kg_extraction, ensure_ascii=False)
    )

    # Optional - clear the graph if the delete flag is set
    if delete:
        delete_all_entries(kg_provider)

    url_map = get_all_yc_co_directory_urls()

    i = 0
    # Ingest and clean the data for each company
    for company, url in url_map.items():
        company_data = fetch_and_clean_yc_co_data(url)
        if i >= max_entries:
            break
        try:
            # Ingest as a text document
            r2r.ingest_documents(
                [
                    Document(
                        id=generate_id_from_label(company),
                        type="txt",
                        data=company_data,
                        metadata={},
                    )
                ]
            )
        except:
            continue
        i += 1

    print_all_relationships(kg_provider)


if __name__ == "__main__":
    fire.Fire(main)
