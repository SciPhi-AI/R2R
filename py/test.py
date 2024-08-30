from sdk import R2RClient

client = R2RClient("http://localhost:8000")

health_response = client.health()
print(health_response)

# register_response = client.register("test@test.com", "password123")
# print(register_response)

login_response = client.login("test@test.com", "password123")
print(login_response)

search_response = client.search("test")
print(search_response)

rag_response = client.rag("test")
print(rag_response)
