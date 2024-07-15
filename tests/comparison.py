import os
import asyncio
import argparse
from typing import AsyncGenerator, List
from r2r.base.abstractions.document import DataType
from r2r.base.parsers.base_parser import AsyncParser

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
    parser.add_argument('--folder', type=str, help='Folder containing the files to be parsed')
    args = parser.parse_args()

    file_list = [
        'pdf_easy.pdf',
        'pdf_hard.pdf',
        'TSLA Q1 2024 Update.pdf',
    ]

    os.makedirs(args.output, exist_ok=True)

    tasks = []
    for file in file_list:
        file_path = os.path.join(args.folder, file)
        for parser_type in [ 'marker']:
            tasks.append(process_file(file_path, parser_type, args.folder))
    
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())