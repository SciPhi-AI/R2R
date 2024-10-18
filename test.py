# test_sync.py

from sdk.client import R2RClient

client = R2RClient()
response = client.login("admin@example.com", "change_me_immediately")
print(response)
client.close()
