import argparse
import os
import time
import uuid

import yaml
from datasets import load_dataset

args = argparse.ArgumentParser()
args.add_argument("--dataset_name", type=str, default="shreyaspimpalgaonkar/ycombinator_s24")
args.add_argument("--split", type=str, default="train")
args.add_argument("--column_name", type=str, default="text")
args.add_argument("--base_url", type=str, default="http://localhost:7272")
args.add_argument("--ingest", action="store_true")
args.add_argument("--ask", action="store_true")
args.add_argument("--query", type=str, default="")
args.add_argument("--kg_search_type", type=str, default="local")
args.add_argument("--num_companies", type=int, required=True, help="Number of companies to ingest, max 255")
args.add_argument("--save_folder", type=str, default=".data")
args = args.parse_args()

client = R2RClient(base_url = args.base_url)

def get_dataset(dataset_name, save_folder = '.data', split = "train", column_name = "text"):
    #make dir
    os.makedirs(save_folder, exist_ok=True)
    data = load_dataset(dataset_name)
    data = data[split].select(range(args.num_companies))
    for item in data:
        file_path = os.path.join(save_folder, f"{item['slug']}.txt")
        # Check if the item contains JSON data
        with open(file_path, "w") as f:
            f.write(item[column_name])
        yield file_path

def wait_till_ready(status_var, status_value):
    while True:
        documents_overview = client.documents_overview(limit=1000)['results']

        # print a percentage contribution of each status value value of status var
        status_counts = {}
        for document in documents_overview:
            print(document.get("name"), document.get(status_var))
            status = document.get(status_var)
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts[status] = 1

        # show fraction of each status value
        for status, count in status_counts.items():
            print(f"{status}: {count / len(documents_overview) * 100:.2f}%")


        if all(document.get(status_var) == status_value for document in documents_overview):
            break
        else:
            # if at least one says failed, exit
            if "failed" in status_counts or "enrichment_failure" in status_counts:
                print(f"At least one document has failed {status_var} => {status_value}")
                for document in documents_overview:
                    if document.get(status_var) == "failed":
                        print(document.get("id"), document.get("status"))
                exit(1)
        time.sleep(10)

def ingest_data():
    print("Ingesting data...")
    for text in get_dataset(args.dataset_name, args.save_folder, args.split, args.column_name):
        client.ingest_files(file_paths=[text])

    # wait till all get ingested
    wait_till_ready("ingestion_status", "success")
    print("Ingested data")


def create_graph():
    print("Creating graph...")
    entity_types = ["ORGANIZATION", "GEO", "PERSON", "INDUSTRY_SECTOR", "PRODUCT", "COMPETITOR", "TECHNOLOGY", "ACQUISITION", "INVESTOR", ]
    documents_overview = client.documents_overview(limit=1000)['results']
    document_ids = [document.get("id") for document in documents_overview if document.get("kg_extraction_status") in ["pending", "failed", "enrichment_failure"]]
    client.create_graph(document_ids = document_ids)
    wait_till_ready("kg_extraction_status", "success")


def enrich_graph():
    print("Enriching graph...")
    client.enrich_graph()
    wait_till_ready("kg_extraction_status", "enriched")

def update_prompts():
    print("Updating prompts...")
    prompts = yaml.load(open("prompts.yaml", "r"), Loader=yaml.FullLoader)
    for prompt_name, prompt in prompts.items():
        client.update_prompt(
            name=prompt_name,
            template=prompt["template"],
            input_types=prompt["input_types"]
        )

def ingest():
    update_prompts()
    ingest_data()
    create_graph()
    enrich_graph()

def ask():
    result = client.rag(query=args.query, use_kg_search=True, kg_search_type=args.kg_search_type)
    print(result)

if __name__ == "__main__":

    if args.ingest and not args.ask:
        ingest()
        print("Ingested data")
    elif args.ask and not args.ingest:
        ask()
    else:
        print("Please provide either --ingest or --ask flag")
        exit(1)
