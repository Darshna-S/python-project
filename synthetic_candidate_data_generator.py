import csv
import random
from faker import Faker

fake = Faker()
CSV_FILE = "synthetic_candidates.csv"
subjects = ["Computer Science", "Data Structures", "Mathematics", "Machine Learning", "Cyber Security"]

print("Generating 20 fake candidate profiles...")

# Open file for writing
with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    
    # Write the column headers
    writer.writerow(["Candidate ID", "Name", "Age", "Email", "Exam Subject"])
    
    # Generate 20 distinct profiles
    for i in range(1, 21):
        c_id = f"CAN2026-{1000 + i}"
        name = fake.name()
        age = random.randint(18, 35)
        # Generate an email matching their generated name context
        email = fake.ascii_free_email()
        subject = random.choice(subjects)
        
        writer.writerow([c_id, name, age, email, subject])

print(f"Success! 20 rows of mockup data written safely to: {CSV_FILE}")
