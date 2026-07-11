import os

FILE_NAME = "candidates.txt"

def add_candidate():
    candidate_id = input("Enter Candidate ID: ").strip()
    name = input("Enter Candidate Name: ").strip()
    email = input("Enter Candidate Email: ").strip()
    
    # Save fields separated by a unique delimiter (like a comma or pipe)
    with open(FILE_NAME, "a") as file:
        file.write(f"{candidate_id},{name},{email}\n")
    print("Candidate written to file storage successfully.")

def display_candidates():
    if not os.path.exists(FILE_NAME) or os.path.getsize(FILE_NAME) == 0:
        print("No candidate data found in the file storage.")
        return
        
    print("\n--- Current Candidate Data ---")
    with open(FILE_NAME, "r") as file:
        for line in file:
            c_id, name, email = line.strip().split(",")
            print(f"ID: {c_id} | Name: {name} | Email: {email}")

def search_candidate():
    if not os.path.exists(FILE_NAME):
        print("No database file found.")
        return
        
    search_id = input("Enter Candidate ID to search: ").strip()
    found = False
    
    with open(FILE_NAME, "r") as file:
        for line in file:
            c_id, name, email = line.strip().split(",")
            if c_id == search_id:
                print(f"\nMatch Found!\nID: {c_id}\nName: {name}\nEmail: {email}")
                found = True
                break
    if not found:
        print("No candidate found matching that ID.")

while True:
    print("\n--- Candidate File Manager ---")
    print("1. Add Candidate to File")
    print("2. Read and Display All Candidates")
    print("3. Search Candidate by ID")
    print("4. Exit")
    
    choice = input("Choice: ").strip()
    if choice == '1': add_candidate()
    elif choice == '2': display_candidates()
    elif choice == '3': search_candidate()
    elif choice == '4': break
    else: print("Invalid entry.")
