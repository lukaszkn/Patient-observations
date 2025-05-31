# generate_patients.py

import argparse
import sqlite3
from faker import Faker
import random
import json


def generate_to_sqlite(db_name="patients.db", count=100):
    start_number = 1
    fake = Faker()
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create the patient table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patient (
            pat_no TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            gender TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            address TEXT NOT NULL
        );
    """)

    new_patients = []

    for i in range(count):
        pat_no = f"PAT{start_number + i:05d}"
        name = fake.name()
        gender = random.choice(["Male", "Female"])
        birth_date = fake.date_of_birth(minimum_age=18, maximum_age=90).isoformat()
        address = fake.address().replace("\n", ", ")
        new_patients.append((pat_no, name, gender, birth_date, address))

    # Insert new patients into the table
    cursor.executemany("""
        INSERT INTO patient (pat_no, name, gender, birth_date, address)
        VALUES (?, ?, ?, ?, ?);
    """, new_patients)

    conn.commit()
    conn.close()


def generate_to_json(file_path="patients.json", count=100):
    start_number = 1
    fake = Faker()
    patients = []

    for i in range(count):
        pat_no = f"PAT{start_number + i:05d}"
        name = fake.name()
        gender = random.choice(["Male", "Female"])
        birth_date = fake.date_of_birth(minimum_age=18, maximum_age=90).isoformat()
        address = fake.address().replace("\n", ", ")

        patients.append({
            "pat_no": pat_no,
            "name": name,
            "gender": gender,
            "birth_date": birth_date,
            "address": address
        })

    # Save to JSON file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(patients, f, indent=4)

    print(f"{count} random patient records saved to {file_path}.")


# Command dispatcher
commands = {
    "sqlite": generate_to_sqlite,
    "json": generate_to_json
}


def main():
    parser = argparse.ArgumentParser(description="Run a command with an argument.")
    parser.add_argument("command", type=str, help=f"Command to run ({', '.join(commands.keys())})")
    parser.add_argument("count", type=int, nargs='?', default=100, help="Patients count")

    args = parser.parse_args()

    command_func = commands.get(args.command)

    if not command_func:
        print(f"Unknown command: {args.command}")
        print(f"Available commands: {', '.join(commands.keys())}")
    else:
        command_func(count=args.count)


if __name__ == "__main__":
    main()
