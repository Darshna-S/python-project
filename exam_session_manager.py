# Initial state can be: "Not Started", "Running", "Paused", "Ended"
status = "Not Started"

while True:
    print(f"\nCurrent Exam Status: [{status}]")
    print("1. Start Exam")
    print("2. Pause Exam")
    print("3. Resume Exam")
    print("4. End Exam")
    print("5. Exit")
    
    choice = input("Select an option (1-5): ").strip()
    
    if choice == '1':
        if status == "Not Started":
            status = "Running"
            print("Exam session started successfully.")
        elif status == "Ended":
            print("Cannot restart. The exam has already ended.")
        else:
            print("The exam is already running or paused.")
            
    elif choice == '2':
        if status == "Running":
            status = "Paused"
            print("Exam session paused.")
        elif status == "Paused":
            print("The exam is already paused.")
        else:
            print("Action invalid. You can only pause a running exam.")
            
    elif choice == '3':
        if status == "Paused":
            status = "Running"
            print("Exam session resumed.")
        elif status == "Running":
            print("The exam is already running.")
        else:
            print("Action invalid. You can only resume from a paused state.")
            
    elif choice == '4':
        if status in ["Running", "Paused"]:
            status = "Ended"
            print("Exam session ended. Submissions finalized.")
        elif status == "Not Started":
            print("Action invalid. You cannot end an exam that hasn't started.")
        else:
            print("The exam has already ended.")
            
    elif choice == '5':
        print("Closing session manager.")
        break
    else:
        print("Invalid selection. Try again.")
