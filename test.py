from r2r import R2RClient

client = R2RClient("http://localhost:8000")

login_response = client.login("admin@example.com", "change_me_immediately")
print(login_response)

search_response = client.search("What was Uber's profit in 2020?")
print(search_response)
