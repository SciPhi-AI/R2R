import os

import fire
import requests
from bs4 import BeautifulSoup, Comment

from r2r import R2RClient, R2RPromptProvider


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
    base_url="http://localhost:7272",
):
    # Specify the entity types for the KG extraction prompt
    entity_types = [
        "COMPANY",
        "SCHOOL",
        "LOCATION",
        "PERSON",
        "DATE",
        "OTHER",
        "QUANTITY",
        "EVENT",
        "INDUSTRY",
        "MEDIA",
    ]

    # Specify the relations for the KG construction
    relations = [
        # Founder Relations
        "EDUCATED_AT",
        "WORKED_AT",
        "FOUNDED",
        # Company relations
        "RAISED",
        "REVENUE",
        "TEAM_SIZE",
        "LOCATION",
        "ACQUIRED_BY",
        "ANNOUNCED",
        "INDUSTRY",
        # Product relations
        "PRODUCT",
        "FEATURES",
        "TECHNOLOGY",
        # Additional relations
        "HAS",
        "AS_OF",
        "PARTICIPATED",
        "ASSOCIATED",
    ]

    client = R2RClient(base_url=base_url)
    r2r_prompts = R2RPromptProvider()

    prompt = "graphrag_triples_extraction_few_shot"

    r2r_prompts.update_prompt(
        prompt,
        input_types={"entity_types": entity_types, "relations": relations},
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


if __name__ == "__main__":
    fire.Fire(main)
