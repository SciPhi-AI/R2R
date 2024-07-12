from collections import namedtuple
import sys
# call unstructured function given an input filename
import os
from unstructured.partition.auto import partition
from r2r import Document, DocumentType
from r2r.pipes import ParsingPipe
import asyncio
import uuid
from nltk.translate.bleu_score import sentence_bleu
import myers

import argparse 
arg = argparse.ArgumentParser()
arg.add_argument('--folder', type=str, help='Folder containing the files to be parsed')
args = arg.parse_args()


def get_parts(filename: str, parser: str):
    if parser == 'unstructured':
        return get_unstructured_parts(filename)
    elif parser == 'r2r':
        return get_r2r_parts(filename)
    elif parser == 'marker':
        return marker_parser(filename)
    else:
        raise ValueError(f"Parser {parser} not found")


# unstructured io
from r2r.parsers import PDFParserUnstructured
def get_unstructured_parts(filename: str):
    unst_parser = PDFParserUnstructured()
    elements = unst_parser.ingest(filename)
    return elements

# r2r
from r2r.parsers import PDFParser
async def get_r2r_parts(filename: str):
    # Create a document
    document = Document(
        id=uuid.uuid4(),
        type=DocumentType.PDF,
        data = open(filename, 'rb').read()
    )
    # Parse the document
    parser = PDFParser()
    parts = parser.ingest(document)
    return parts

from r2r.parsers import PDFParserMarker
def marker_parser(file_path): 
    parser = PDFParserMarker()
    with open(file_path, 'rb') as file:
        text, _, _ = parser.ingest(file.read())
    return text

def post_process_parts(parts: list, parser: str):
    if parser == 'unstructured':
        return post_process_unstructured_parts(parts)
    elif parser == 'r2r':
        return post_process_r2r_parts(parts)
    elif parser == 'marker':
        return parts
    else:
        raise ValueError(f"Parser {parser} not found")

def post_process_unstructured_parts(parts: list):
    # Post process the unstructured
    texts = []
    for part in parts:
        try:
            texts.append(part.text)
        except:
            print(part.__dict__)
            import pdb; pdb.set_trace()

    return  "\n\n===============\n\n".join(texts)

def post_process_r2r_parts(parts: list):
    texts = []
    for part in parts:
        texts.append(part.data)
    return "\n\n===============\n\n".join(texts)

def post_process_marker_parts(parts: list):
    texts = []
    for part in parts:
        texts.append(part)
    return "\n\n===============\n\n".join(texts)

def main():
    # Create the parsing pipe
    # pipe = ParsingPipe([])

    file_list = [
        # 'cambridge.ppt', 
        # 'dotcom.html', 
        'pdf_easy.pdf',
        'pdf_hard.pdf',
        'TSLA Q1 2024 Update.pdf',
        # 'word_doc.dox'
    ]

    for file in file_list:

        try:
            file_path = os.path.join(args.folder, file)

            # Get the parts
            for parser in ['unstructured', 'r2r', 'marker']:
                parts = get_parts(file_path, parser)
                text = post_process_parts(parts, parser)
                with open(f'{file}_{parser}.txt', 'w') as f:
                    f.write(text)

        except Exception as e: 
            print(f"Error parsing file {file_path}")
            print(e)
            continue

if __name__ == '__main__':
    main()