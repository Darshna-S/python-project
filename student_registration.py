students = []

while True:
    print("\n--- Student Registration System ---")
    print("1. Register New Student")
    print("2. Display All Students")
    print("3. Search Student by ID")
    print("4. Delete Student")
    print("5. Exit")
    
    choice = input("Enter choice (1-5): ").strip()
    
    if choice == '1':
        student_id = input("Enter Student ID: ").strip()
        name = input("Enter Student Name: ").strip()
        # Prevent duplicate IDs
        if any(s['id'] == student_id for s in students):
            print("Error: A student with this ID already exists.")
        else:
            students.append({"id": student_id, "name": name})
            print(f"Student '{name}' registered successfully!")
            
    elif choice == '2':
        if not students:
            print("No students registered yet.")
        else:
            print("\nRegistered Students:")
            for s in students:
                print(f"ID: {s['id']} | Name: {s['name']}")
                
    elif choice == '3':
        search_id = input("Enter Student ID to search: ").strip()
        found = next((s for s in students if s['id'] == search_id), None)
        if found:
            print(f"Found! ID: {found['id']} | Name: {found['name']}")
        else:
            print("Student not found.")
            
    elif choice == '4':
        delete_id = input("Enter Student ID to delete: ").strip()
        initial_count = len(students)
        students = [s for s in students if s['id'] != delete_id]
        if len(students) < initial_count:
            print("Student record deleted successfully.")
        else:
            print("Student ID not found.")
            
    elif choice == '5':
        print("Exiting program.")
        break
    else:
        print("Invalid choice! Please select between 1 and 5.")
