from r2r import R2RClient

if __name__ == "__main__":
    client = R2RClient(
        "http://localhost:7272"
    )  # Replace with your R2R deployment URL

    # Register a new user
    user_result = client.register("user11123@test.com", "password123")
    print(user_result)

    # # Uncomment when running with authentication
    # # Verify email (replace with actual verification code sent to the user's email)
    # verify_result = client.verify_email("verification_code_here")
    # print(verify_result)

    # Login immediately (assuming email verification is disabled)
    login_result = client.login("user11123@test.com", "password123")
    print(login_result)

    # Refresh access token
    refresh_result = client.refresh_access_token()
    print(refresh_result)

    import os

    # Ingest a sample file for the logged-in user
    script_path = os.path.dirname(__file__)
    sample_file = os.path.join(script_path, "..", "data", "aristotle.txt")
    ingestion_result = client.ingest_files([sample_file])
    print(ingestion_result)

    # Check the user's documents
    documents_overview = client.documents_overview()
    print(documents_overview)

    # Check that we can search and run RAG over the user documents
    search_result = client.search(query="Sample search query")
    print(search_result)

    rag_result = client.rag(query="Sample search query")
    print(rag_result)

    # # Uncomment to delete the user account
    # # Delete account (requires password confirmation)
    # delete_result = client.delete_user(login_result["id"], "password123")
    # print(delete_result)

    logout_result = client.logout()
    print(logout_result)
    # {'results': {'message': 'Logged out successfully'}}

    # # Login as admin
    login_result = client.login("admin@example.com", "change_me_immediately")

    # Now you can access superuser features, for example:
    users_overview = client.users_overview()
    print(users_overview)

    # Access system-wide logs
    logs = client.logs()
    print(logs)

    # Perform analytics
    analytics_result = client.analytics(
        {"search_latencies": "search_latency"},
        {"search_latencies": ["basic_statistics", "search_latency"]},
    )
    print(analytics_result)
