import os
import asyncio
import argparse
from typing import AsyncGenerator, List
from r2r.base.abstractions.document import DataType
from r2r.base.parsers.base_parser import AsyncParser
import time

import os
os.environ['PYTORCH_ENABLE_MPS_FALLBACK']='1'

# Import parsers
from r2r.parsers import PDFParserUnstructured, PDFParser, PDFParserMarker

async def get_parts(filename: str, parser: str) -> AsyncGenerator[str, None]:
    
    with open(filename, 'rb') as file:
        data = file.read()
    
    if parser == 'unstructured':
        parser_instance = PDFParserUnstructured()
    elif parser == 'r2r':
        parser_instance = PDFParser()
    elif parser == 'marker':
        parser_instance = PDFParserMarker()
    else:
        raise ValueError(f"Parser {parser} not found")
    
    async for part in parser_instance.ingest(data):
        yield part

async def post_process_parts(parts: AsyncGenerator[str, None], parser: str) -> str:
    texts = []
    async for part in parts:
        if parser == 'unstructured':
            texts.append(part)
        elif parser == 'r2r':
            texts.append(part)
        elif parser == 'marker':
            texts.append(part)
        else:
            raise ValueError(f"Parser {parser} not found")
    
    return "\n\n===============\n\n".join(texts)

async def process_file(file_path: str, parser: str, output_folder: str):
    # try:
    parts = get_parts(file_path, parser)
    text = await post_process_parts(parts, parser)
    output_file = os.path.join(output_folder, f"{os.path.basename(file_path)}_{parser}.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Processed {file_path} with {parser}")
    # except Exception as e:
    #     print(f"Error parsing file {file_path} with {parser}: {str(e)}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=str, help='Folder containing the files to be parsed', default= '/Users/shreyas/code/parsing/data/sample_files')
    args = parser.parse_args()

    file_list = [
        'pdf_easy.pdf',
        'pdf_hard.pdf',
        'TSLA.pdf',
    ]

    results = {}  # Dictionary to store processing times

    for file in file_list:
        file_path = os.path.join(args.folder, file)
        results[file] = {} 

        # for parser_type in ['r2r', 'unstructured', 'marker']:
        for parser_type in ['unstructured']:
            start_time = time.time()
            await process_file(file_path, parser_type, args.folder) 
            end_time = time.time()  

            # Store the processing time
            results[file][parser_type] = end_time - start_time

    # Print the results in a tabular format
    print("File Processing Times (seconds):")
    print(f"{'File':<20} {'r2r':<10} {'unstructured':<15} {'marker':<10}")
    for file, times in results.items():
        print(f"{file:<20} {times['r2r']:<10.2f} {times['unstructured']:<15.2f} {times['marker']:<10.2f}")

if __name__ == '__main__':
    asyncio.run(main())