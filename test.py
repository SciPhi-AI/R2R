import os

from r2r import R2RClient

client = R2RClient(
    "http://localhost:8000"
)  # Replace with your R2R deployment URL

# Register a new user
# user_result = client.register("user1@test.com", "password123")
# {'results': {'email': 'user1@test.com', 'id': 'bf417057-f104-4e75-8579-c74d26fcbed3', 'hashed_password': '$2b$12$p6a9glpAQaq.4uzi4gXQru6PN7WBpky/xMeYK9LShEe4ygBf1L.pK', 'is_superuser': False, 'is_active': True, 'is_verified': False, 'verification_code_expiry': None, 'name': None, 'bio': None, 'profile_picture': None, 'created_at': '2024-07-16T22:53:47.524794Z', 'updated_at': '2024-07-16T22:53:47.524794Z'}}

# Ingest a file

# Login immediately (assuming email verification is disabled)
login_result = client.login("user1@test.com", "password123")
# {'results': {'access_token': {'token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMUB0ZXN0LmNvbSIsImV4cCI6MTcyMTE5OTI0Ni44Nzc2NTksInRva2VuX3R5cGUiOiJhY2Nlc3MifQ.P4RcCkCe0H5UHPHak7tRovIgyQcql4gB8NlqdDDk50Y', 'token_type': 'access'}, 'refresh_token': {'token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMUB0ZXN0LmNvbSIsImV4cCI6MTcyMTc3NTI0NiwidG9rZW5fdHlwZSI6InJlZnJlc2gifQ.VgfZ4Lhz0f2GW41NYv6KLrMCK3CdGmGVug7eTQp0xPU', 'token_type': 'refresh'}}}

sample_file = os.path.join("r2r/examples/data/aristotle.txt")
ingestion_result = client.ingest_files([sample_file])
