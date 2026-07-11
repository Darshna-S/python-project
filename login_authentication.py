# Pre-registered credentials
user_db = {
    "admin": "password123",
    "user1": "securepass",
    "flask_dev": "python310"
}

attempts = 0
max_attempts = 3

print("--- Secure Login System ---")

while attempts < max_attempts:
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    
    if username in user_db and user_db[username] == password:
        print("\nLogin Successful! Welcome to the system.")
        break
    else:
        attempts += 1
        remaining = max_attempts - attempts
        print(f"Incorrect credentials. Remaining attempts: {remaining}")
        
if attempts == max_attempts:
    print("\nAccount Locked! You have exceeded 3 failed login attempts.")
