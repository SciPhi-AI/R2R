"""migrate_to_document_search.

Revision ID: 2fac23e4d91b
Revises:
Create Date: 2024-11-11 11:55:49.461015
"""

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.types import UserDefinedType

from r2r import R2RAsyncClient

# revision identifiers, used by Alembic.
revision: str = "2fac23e4d91b"
down_revision: Union[str, None] = "d342e632358a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

project_name = os.getenv("R2R_PROJECT_NAME")
if not project_name:
    raise ValueError(
        "Environment variable `R2R_PROJECT_NAME` must be provided migrate, it should be set equal to the value of `project_name` in your `r2r.toml`."
    )

dimension = os.getenv("R2R_EMBEDDING_DIMENSION")
if not dimension:
    raise ValueError(
        "Environment variable `R2R_EMBEDDING_DIMENSION` must be provided migrate, it must should be set equal to the value of `base_dimension` in your `r2r.toml`."
    )


class Vector(UserDefinedType):
    def get_col_spec(self, **kw):
        return f"vector({dimension})"


def run_async(coroutine):
    """Helper function to run async code synchronously."""
    with ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, coroutine).result()


async def async_generate_all_summaries():
    """Asynchronous function to generate summaries."""

    base_url = os.getenv("R2R_BASE_URL")
    if not base_url:
        raise ValueError(
            "Environment variable `R2R_BASE_URL` must be provided, it must point at the R2R deployment you wish to migrate, e.g. `http://localhost:7272`."
        )

    print(f"Using R2R Base URL: {base_url})")

    base_model = os.getenv("R2R_BASE_MODEL")
    if not base_model:
        raise ValueError(
            "Environment variable `R2R_BASE_MODEL` must be provided, e.g. `openai/gpt-4o-mini`, it will be used for generating document summaries during migration."
        )

    print(f"Using R2R Base Model: {base_model}")

    client = R2RAsyncClient(base_url)

    offset = 0
    limit = 1_000
    documents = (await client.documents_overview(offset=offset, limit=limit))[
        "results"
    ]
    while len(documents) == limit:
        limit += offset
        documents += (
            await client.documents_overview(offset=offset, limit=limit)
        )["results"]

    # Load existing summaries if they exist
    document_summaries = {}
    if os.path.exists("document_summaries.json"):
        try:
            with open("document_summaries.json", "r") as f:
                document_summaries = json.load(f)
            print(
                f"Loaded {len(document_summaries)} existing document summaries"
            )
        except json.JSONDecodeError:
            print(
                "Existing document_summaries.json was invalid, starting fresh"
            )
            document_summaries = {}

    for document in documents:
        title = document["title"]
        doc_id = str(
            document["id"]
        )  # Convert UUID to string for JSON compatibility

        # Skip if document already has a summary
        if doc_id in document_summaries:
            print(
                f"Skipping document {title} ({doc_id}) - summary already exists"
            )
            continue

        print(f"Processing document: {title} ({doc_id})")

        try:
            document_text = f"Document Title:{title}\n"
            if document["metadata"]:
                metadata = json.dumps(document["metadata"])
                document_text += f"Document Metadata:\n{metadata}\n"

            full_chunks = (
                await client.document_chunks(document["id"], limit=10)
            )["results"]

            document_text += "Document Content:\n"

            for chunk in full_chunks:
                document_text += chunk["text"]

            summary_prompt = """## Task:

    Your task is to generate a descriptive summary of the document that follows. Your objective is to return a summary that is roughly 10% of the input document size while retaining as many key points as possible. Your response should begin with `The document contains `.

    ### Document:

    {document}


    ### Query:

    Reminder: Your task is to generate a descriptive summary of the document that was given. Your objective is to return a summary that is roughly 10% of the input document size while retaining as many key points as possible. Your response should begin with `The document contains `.

    ## Response:"""

            messages = [
                {
                    "role": "user",
                    "content": summary_prompt.format(
                        **{"document": document_text}
                    ),
                }
            ]
            summary = await client.completion(
                messages=messages, generation_config={"model": base_model}
            )
            summary_text = summary["results"]["choices"][0]["message"][
                "content"
            ]
            embedding_vector = await client.embedding(summary_text)
            # embedding_response = await openai_client.embeddings.create(
            #     model=embedding_model, input=summary_text, dimensions=dimension
            # )
            # embedding_vector = embedding_response.data[0].embedding

            # Store in our results dictionary
            document_summaries[doc_id] = {
                "summary": summary_text,
                "embedding": embedding_vector,
            }

            # Save after each document
            with open("document_summaries.json", "w") as f:
                json.dump(document_summaries, f)

            print(f"Successfully processed document {doc_id}")

        except Exception as e:
            print(f"Error processing document {doc_id}: {str(e)}")
            # Continue with next document instead of failing
            continue

    return document_summaries


def generate_all_summaries():
    """Synchronous wrapper for async_generate_all_summaries."""
    return run_async(async_generate_all_summaries())


def check_if_upgrade_needed():
    """Check if the upgrade has already been applied or is needed."""
    # Get database connection
    connection = op.get_bind()
    inspector = inspect(connection)

    # First check if the document_info table exists
    if not inspector.has_table("document_info", schema=project_name):
        print(
            f"Migration not needed: '{project_name}.document_info' table doesn't exist yet"
        )
        return False

    # Then check if the columns exist
    existing_columns = [
        col["name"]
        for col in inspector.get_columns("document_info", schema=project_name)
    ]

    needs_upgrade = "summary" not in existing_columns

    if needs_upgrade:
        print(
            "Migration needed: 'summary' column does not exist in document_info table"
        )
    else:
        print(
            "Migration not needed: 'summary' column already exists in document_info table"
        )

    return needs_upgrade


def upgrade() -> None:
    if check_if_upgrade_needed():
        # Load the document summaries
        generate_all_summaries()
        document_summaries = None
        try:
            with open("document_summaries.json", "r") as f:
                document_summaries = json.load(f)
            print(f"Loaded {len(document_summaries)} document summaries")
        except FileNotFoundError:
            print(
                "document_summaries.json not found. Continuing without summaries and/or summary embeddings."
            )
            pass
        except json.JSONDecodeError:
            raise ValueError("Invalid document_summaries.json file") from None

        # Create the vector extension if it doesn't exist
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Add new columns to document_info
        op.add_column(
            "document_info",
            sa.Column("summary", sa.Text(), nullable=True),
            schema=project_name,
        )

        op.add_column(
            "document_info",
            sa.Column("summary_embedding", Vector, nullable=True),
            schema=project_name,
        )

        # Add generated column for full text search
        op.execute(f"""
        ALTER TABLE {project_name}.document_info
        ADD COLUMN doc_search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(summary, '')), 'B') ||
            setweight(to_tsvector('english', COALESCE((metadata->>'description')::text, '')), 'C')
        ) STORED;
        """)

        # Create index for full text search
        op.execute(f"""
        CREATE INDEX idx_doc_search_{project_name}
        ON {project_name}.document_info
        USING GIN (doc_search_vector);
        """)

        if document_summaries:
            # Update existing documents with summaries and embeddings
            for doc_id, doc_data in document_summaries.items():
                # Convert the embedding array to the PostgreSQL vector format
                embedding_str = (
                    f"[{','.join(str(x) for x in doc_data['embedding'])}]"
                )

                # Use plain SQL with proper escaping for PostgreSQL
                op.execute(f"""
                    UPDATE {project_name}.document_info
                    SET
                        summary = '{doc_data["summary"].replace("'", "''")}',
                        summary_embedding = '{embedding_str}'::vector({dimension})
                    WHERE document_id = '{doc_id}'::uuid;
                    """)
        else:
            print(
                "No document summaries found, skipping update of existing documents"
            )


def downgrade() -> None:
    # First drop any dependencies on the columns we want to remove
    op.execute(f"""
        -- Drop the full text search index first
        DROP INDEX IF EXISTS {project_name}.idx_doc_search_{project_name};

        -- Drop the generated column that depends on the summary column
        ALTER TABLE {project_name}.document_info
        DROP COLUMN IF EXISTS doc_search_vector;
        """)

    # Now we can safely drop the summary and embedding columns
    op.drop_column("document_info", "summary_embedding", schema=project_name)
    op.drop_column("document_info", "summary", schema=project_name)
