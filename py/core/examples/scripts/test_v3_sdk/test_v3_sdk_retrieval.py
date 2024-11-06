from r2r import R2RClient

user_email = "John.Doe1@email.com"

client = R2RClient("http://localhost:7276", prefix="/v3")

# Login
result = client.users.login(
    email=user_email, password="new_secure_password123"
)
print("Login successful")

# Test 1: Search retrieval
print("\n=== Test 1: Search Retrieval ===")
search_result = client.retrieval.search(query="whoami?")
print("Search results:", search_result)

# Test 2: Another search retrieval (for demonstration)
print("\n=== Test 2: Another Search Retrieval ===")
search_result_2 = client.retrieval.search(query="what is the meaning of life?")
print("Search results 2:", search_result_2)
