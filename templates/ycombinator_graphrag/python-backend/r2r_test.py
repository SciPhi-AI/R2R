import time
import uuid
import os
from r2r import R2RClient
from datasets import load_dataset
import argparse

args = argparse.ArgumentParser()
args.add_argument("--dataset_name", type=str, default="shreyaspimpalgaonkar/yc_s24")
args.add_argument("--split", type=str, default="train")
args.add_argument("--column_name", type=str, default="text")
args.add_argument("--base_url", type=str, default="http://localhost:7272")
args.add_argument("ingest", action="store_true")
args.add_argument("ask", action="store_true")
args.add_argument("--query", type=str, default="")
args.add_argument("--kg_search_type", type=str, default="local")
args = args.parse_args()

client = R2RClient(base_url = args.base_url)

def get_dataset(dataset_name, save_folder = '.data', split = "train", column_name = "text"):
    #make dir
    os.makedirs(save_folder, exist_ok=True)
    data = load_dataset(dataset_name)
    for item in data[split].iter_rows():
        file_path = os.path.join(save_folder, f"{item['id']}.txt")
        with open(file_path, "w") as f:
            f.write(item[column_name])
        yield file_path


def generate_id_from_label(label: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, label)


def wait_till_ready(status_var, status_value):
    while True:
        documents_overview = client.get_documents_overview()
        if all(document.get(status_var) == status_value for document in documents_overview):
            break
        time.sleep(10)

def ingest_data():
    for text in get_dataset(args.dataset_name, args.split, args.column_name):
        result = client.ingest_files(file_paths=[text])
        print(result)

    # wait till all get ingested 
    wait_till_ready("ingestion_status", "success")


def create_graph():
    client.create_graph()
    wait_till_ready("restructure_status", "success")


def enrich_graph():
    client.enrich_graph()
    wait_till_ready("restructure_status", "enriched")

def ingest():
    ingest_data()
    create_graph()
    enrich_graph()
    
def ask():
    result = client.rag(query=args.query, use_kg_search=True, kg_search_type=args.kg_search_type)
    print(result)

if __name__ == "__main__":
    if args.ingest and not args.ask:
        ingest()
    elif args.ask and not args.ingest:
        ask()
    else:
        print("Please provide either --ingest or --ask flag")
        exit(1)