from pyspark.sql import SparkSession
import argparse

def join_patient_data(spark, observations_path, patients_path):
    """
    Joins observation data with patient demographic data.

    :param spark: SparkSession object.
    :param observations_path: Path to the observations JSON file.
    :param patients_path: Path to the patients JSON file.
    """
    # Read the JSON data
    observations_df = spark.read.json(observations_path)
    patients_df = spark.read.json(patients_path)

    # Join the two dataframes on the patient number
    joined_df = observations_df.join(patients_df, "pat_no")

    # Show the results
    joined_df.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations_path", default="data/observations_micro.json", help="Path to the observations data")
    parser.add_argument("--patients_path", default="data/patients_micro.json", help="Path to the patients data")
    args = parser.parse_args()

    spark = SparkSession.builder \
        .appName("PatientDataJoin") \
        .getOrCreate()

    join_patient_data(spark, args.observations_path, args.patients_path)

    spark.stop()
