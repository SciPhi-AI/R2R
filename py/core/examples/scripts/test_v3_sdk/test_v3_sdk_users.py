import random
import string

from r2r import R2RClient

# user_email = "John.Doe1@email.com"


# Function to generate a random email
def generate_random_email():
    username_length = 8
    username = "".join(
        random.choices(
            string.ascii_lowercase + string.digits, k=username_length
        )
    )
    domain = random.choice(
        ["example.com", "test.com", "fake.org", "random.net"]
    )
    return f"{username}@{domain}"


user_email = generate_random_email()

client = R2RClient("http://localhost:7276", prefix="/v3")

# Test 1: Register user
print("\n=== Test 1: Register User ===")
register_result = client.users.register(
    email=user_email, password="secure_password123"
)
print("Registered user:", register_result)

# Test 2: Login user
print("\n=== Test 2: Login User ===")
login_result = client.users.login(
    email=user_email, password="secure_password123"
)
print("Login result:", login_result)

# Test 3: Refresh token
print("\n=== Test 3: Refresh Token ===")
refresh_result = client.users.refresh_token()
print("Refresh token result:", refresh_result)

# Test 4: Change password
print("\n=== Test 4: Change Password ===")
change_password_result = client.users.change_password(
    "secure_password123", "new_secure_password123"
)
print("Change password result:", change_password_result)

# Test 5: Request password reset
print("\n=== Test 5: Request Password Reset ===")
reset_request_result = client.users.request_password_reset(email=user_email)
print("Password reset request result:", reset_request_result)

# logout, to use super user
# Test 9: Logout user
print("\n=== Test 6: Logout User ===")
logout_result = client.users.logout()
print("Logout result:", logout_result)

# Test 6: List users
print("\n=== Test 7: List Users ===")
users_list = client.users.list()
print("Users list:", users_list)

# Test 7: Retrieve user
print("\n=== Test 8: Retrieve User ===")
user_id = users_list["results"][0][
    "user_id"
]  # Assuming we have at least one user
user_details = client.users.retrieve(id=user_id)
print("User details:", user_details)

# Test 8: Update user
print("\n=== Test 9: Update User ===")
update_result = client.users.update(user_id, name="Jane Doe")
print("Update user result:", update_result)
