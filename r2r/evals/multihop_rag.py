# doing an eval on multihop rag
# ingest files using R2R and then querying the r2r engine
import asyncio
import re
import argparse
import os
import time
from pathlib import Path
from r2r import R2R, R2RClient
from datasets import load_dataset
from fastapi import UploadFile
from r2r import GenerationConfig, R2RPromptProvider, VectorSearchSettings
from r2r import Document, generate_id_from_label


def select_files_for_upload(folder, force=False, data_len=10):
    # check if folder doesn't exist
    if not os.path.exists(folder) or force:
        # remove dir
        if os.path.exists(folder):
            os.system(f"rm -rf {folder}")

        os.makedirs(folder, exist_ok=True)
        data = load_dataset('json', data_files = '/Users/shreyas/code/parsing/R2R/r2r/evals/corpus.json')
        for i in range(min(len(data['train']), data_len)):
            with open(f"{folder}/{i}.txt", "w") as f:
                keys = ['title', 'author', 'source', 'published_at', 'category', 'url', 'body']
                for key in keys:
                    if key in data['train'][i] and data['train'][i][key] is not None:
                        f.write(f"{key.capitalize()}: ")
                        f.write(str(data['train'][i][key]))
                        f.write("\n\n")

# def run_r2r(self, files: list[str]):
# select_files_for_upload('/Users/shreyas/code/parsing/R2R/r2r/evals/examples', force=True)

async def ingest_into_r2r(app, folder):
    # print("Ingesting into r2r")
    # paths = []
    # for filename in os.listdir(folder):
    #     # get path
    #     upload_file = UploadFile(filename=filename, file=open(os.path.join(folder, filename), "rb"))
    #     paths.append(upload_file)
    # print(paths)

    # paths = []
    # print(folder)
    # print(os.listdir(folder)[:10])
    # for filename in os.listdir(folder):
    #     with open(os.path.join(folder, filename), 'r') as f:
    #         doc = Document(
    #             id = generate_id_from_label(filename),
    #             type = "txt",
    #             data = f.read(),
    #             metadata = {"title": filename}
    #         )
    #         paths.append(doc)
    #     print(paths)
    # res = await app.ingest_documents(paths)

    files = []
    for filename in os.listdir(folder):
        files.append(os.path.join(folder, filename))
    res = app.ingest_files(files)

def get_multihop_rag_dataset():
    return load_dataset('json', data_files = 'https://raw.githubusercontent.com/yixuantt/MultiHop-RAG/main/dataset/MultiHopRAG.json')

async def query_r2r_engine(app, question):
    result = app.rag(question, rag_generation_config = {"model":"gpt-3.5-turbo", "temperature":"0.5"})
    out_data = result['results']['completion']
    return out_data

def get_r2r_app(id):
    password = 'znHKt2OxB0gGzroW'
    url = 'https://wnxriysflkrpxeonraly.supabase.co'
    host = 'aws-0-us-east-1.pooler.supabase.com'
    database_name = f'postgres'
    port = '6543'
    user = 'postgres.wnxriysflkrpxeonraly'

    os.environ['POSTGRES_PASSWORD'] = password
    os.environ['POSTGRES_VECS_COLLECTION']=f'demo_vecs_{id}'
    os.environ['POSTGRES_HOST'] = host
    os.environ['POSTGRES_DBNAME'] = database_name
    os.environ['POSTGRES_USER'] = user
    os.environ['POSTGRES_PORT'] = port
    client = R2RClient(base_url='http://localhost:8000')
    return client

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=str, help='Folder containing the files to be parsed', default= '/Users/shreyas/code/parsing/R2R/r2r/evals/examples')
    parser.add_argument('--ing', action='store_true', help='Ingest files into R2R')
    parser.add_argument('--add_files', action='store_true', help='Force add files')
    parser.add_argument('--num_files', type=int, help='Number of files to ingest', default=10)
    parser.add_argument('--id', type=str, help='Supabase Postgres')
    parser.add_argument('--num_qns', type=int, help='Number of files to ingest', default=10)
    parser.add_argument('--start', type=int, help='Number of files to ingest', default=10)
    args = parser.parse_args()

    select_files_for_upload(args.folder, force=args.add_files, data_len=args.num_files)
    
    app  = get_r2r_app(args.id)

    if args.ing:
        res = await ingest_into_r2r(app, args.folder)
        print('ingested')

    dataset = get_multihop_rag_dataset()
    correct = 0
    incorrect = 0
    for question in dataset['train'].select(range(args.start, min(len(dataset['train']), args.start + args.num_qns))):
        answer = await query_r2r_engine(app, question['query'])
        answer = answer['choices'][0]['message']['content']

        print("===============================")
        print(f"Question: {question['query']}")
        print(f"Reference Answer: {question['answer']}")
        
        try:
            # parse $$$answer$$$ to get the answer
            print(f"Answer: {answer}")
            answer = re.search(r'\$\$\$(.*)\$\$\$', answer).group(1)
            if answer.lower() == question['answer'].lower():
                correct += 1
            else:
                incorrect += 1
        except:
            incorrect += 1

        
    print(f"Correct: {correct}, Incorrect: {incorrect}, Total: {args.num_files}")

if __name__ == '__main__':
    asyncio.run(main())