import csv
from faker import Faker
import random

fake = Faker()
subjects = ['Mathematics', 'Computer Science', 'Physics', 'Chemistry', 'Data Structures']

# Generate 20 sample records
with open('synthetic_candidates.csv', mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    # Writing headers matching the internship requirements
    writer.writerow(['Candidate ID', 'Name', 'Email', 'Age', 'Exam Subject'])
    
    for _ in range(20):
        c_id = f"CAND{random.randint(1000, 9999)}"
        name = fake.name()
        email = fake.email()
        age = random.randint(18, 30)
        subject = random.choice(subjects)
        
        writer.writerow([c_id, name, email, age, subject])

print("✅ Success: 'synthetic_candidates.csv' generated with 20 records.")
