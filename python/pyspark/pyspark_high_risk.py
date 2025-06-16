from pyspark.sql import SparkSession
from pyspark.sql.functions import avg
import argparse

def find_high_risk_patients(spark, input_path, threshold):
    """
    Finds high-risk patients based on an average score threshold.

    :param spark: SparkSession object.
    :param input_path: Path to the observations JSON file.
    :param threshold: The average score threshold for identifying high-risk patients.
    """
    # Read the JSON data
    df = spark.read.json(input_path)

    # Group by patient number and calculate the average score
    avg_score_df = df.groupBy("pat_no").agg(avg("total_score").alias("average_score"))

    # Filter for patients with an average score above the threshold
    high_risk_df = avg_score_df.filter(avg_score_df.average_score > threshold)

    # Show the results
    high_risk_df.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_path", default="data/observations_micro.json", help="Path to the observations data")
    parser.add_argument("--threshold", type=float, default=5.0, help="Risk threshold")
    args = parser.parse_args()

    spark = SparkSession.builder \
        .appName("HighRiskPatients") \
        .getOrCreate()

    find_high_risk_patients(spark, args.input_path, args.threshold)

    spark.stop()
