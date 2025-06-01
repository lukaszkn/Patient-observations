import argparse
import datetime
import random


def create_random_observation(pat_no: str, past_minutes: int = 200) -> dict:
    temperature = round(random.uniform(35.0, 40.0), 1)
    resp_rate = random.randint(12, 30)
    heart_rate = random.randint(60, 140)
    bp_sys = random.randint(90, 160)
    bp_dia = random.randint(60, 100)
    spo2 = random.randint(85, 100)
    consciousness = random.randint(0, 3)

    # Score logic
    temp_score = 2 if temperature >= 39 else 1 if temperature >= 37.5 else 0
    resp_score = 2 if resp_rate > 25 else 1 if resp_rate > 20 else 0
    hr_score = 2 if heart_rate > 120 else 1 if heart_rate > 100 else 0
    bp_score = 1 if bp_sys > 140 or bp_dia > 90 else 0
    spo2_score = 2 if spo2 < 90 else 1 if spo2 < 95 else 0
    cons_score = consciousness  # already 0–3

    total_score = temp_score + resp_score + hr_score + bp_score + spo2_score + cons_score

    readings = [
        {"type": "temperature", "value": temperature, "score": temp_score},
        {"type": "respiratory_rate", "value": resp_rate, "score": resp_score},
        {"type": "heart_rate", "value": heart_rate, "score": hr_score},
        {"type": "blood_pressure_systolic", "value": bp_sys, "score": 0},
        {"type": "blood_pressure_diastolic", "value": bp_dia, "score": bp_score},
        {"type": "oxygen_saturation", "value": spo2, "score": spo2_score},
        {"type": "consciousness_level", "value": consciousness, "score": cons_score}
    ]

    return {
        "pat_no": pat_no,
        "timestamp": (datetime.datetime.now() - datetime.timedelta(minutes=random.uniform(0, past_minutes))).isoformat(),
        "total_score": total_score,
        "readings": readings
    }


def setup_reading_type_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reading_type (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
    """)

    # Only insert if empty
    cursor.execute("SELECT COUNT(*) FROM reading_type;")
    if cursor.fetchone()[0] == 0:
        predefined_types = [
            'temperature',
            'respiratory_rate',
            'heart_rate',
            'blood_pressure_systolic',
            'blood_pressure_diastolic',
            'oxygen_saturation',
            'consciousness_level'
        ]
        cursor.executemany("INSERT INTO reading_type (name) VALUES (?);",
                           [(name,) for name in predefined_types])
        print("Inserted extended reading types.")


def generate_sqlite_observations(db_name="patients.db", count=10, patient_count=100, past_minutes: int = 200):
    import sqlite3
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Ensure required tables
    cursor.execute("""CREATE TABLE IF NOT EXISTS observation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pat_no TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        total_score INTEGER NOT NULL
    );""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS reading (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        observation_id INTEGER NOT NULL,
        reading_type_id INTEGER NOT NULL,
        value REAL NOT NULL,
        score INTEGER NOT NULL,
        FOREIGN KEY (observation_id) REFERENCES observation(id),
        FOREIGN KEY (reading_type_id) REFERENCES reading_type(id)
    );""")

    # Ensure reading_type table
    setup_reading_type_table(cursor)

    # Map type name to ID
    cursor.execute("SELECT id, name FROM reading_type;")
    reading_type_map = {name: rid for rid, name in cursor.fetchall()}

    for _ in range(count):
        pat_no = f"PAT{random.randint(1, patient_count):05d}"
        obs = create_random_observation(pat_no, past_minutes=past_minutes)

        cursor.execute("INSERT INTO observation (pat_no, timestamp, total_score) VALUES (?, ?, ?);",
                       (obs["pat_no"], obs["timestamp"], obs["total_score"]))
        obs_id = cursor.lastrowid

        cursor.executemany(
            "INSERT INTO reading (observation_id, reading_type_id, value, score) VALUES (?, ?, ?, ?);",
            [(obs_id, reading_type_map[r["type"]], r["value"], r["score"]) for r in obs["readings"]]
        )

    conn.commit()
    conn.close()
    print(f"{count} random observations added to database.")


def generate_random_observations_to_json(json_file="observations.json", count=10, patient_count=100, past_minutes: int = 200):
    import json

    observations = [create_random_observation(pat_no=f"PAT{random.randint(1, patient_count):05d}",
                                              past_minutes=past_minutes) for _ in range(count)]

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(observations, f, indent=4)

    print(f"{count} random observations saved to {json_file}")


def main():
    parser = argparse.ArgumentParser(description="Command dispatcher for patient data.")
    parser.add_argument("command", help="Command to run")
    parser.add_argument("count", help="Number of obs to generate", nargs='?', default=100)
    parser.add_argument("patient_count", help="Patients count", nargs='?', default=100)
    parser.add_argument("past_minutes", help="Obs reading time minutes in the past", nargs='?', default=200)

    args = parser.parse_args()
    command = args.command
    count = int(args.count) if args.count and args.count.isdigit() else 100
    patient_count = int(args.count) if args.patient_count and args.patient_count.isdigit() else 100
    past_minutes = int(args.past_minutes) if args.past_minutes and args.past_minutes.isdigit() else 200

    if command == "sqlite":
        generate_sqlite_observations(count=count, patient_count=patient_count, past_minutes=past_minutes)
    elif command == "json":
        generate_random_observations_to_json(count=count, patient_count=patient_count, past_minutes=past_minutes)
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
