from pyspark.sql import SparkSession
from pyspark.sql.functions import avg

def calculate_average_score(spark, input_path):
    """
    Calculates the average total_score for each patient.

    :param spark: SparkSession object.
    :param input_path: Path to the observations JSON file.
    """
    # Read the JSON data
    df = spark.read.json(input_path)

    # Group by patient number and calculate the average score
    avg_score_df = df.groupBy("pat_no").agg(avg("total_score").alias("average_score"))

    # Show the results
    avg_score_df.show()

if __name__ == "__main__":
    spark = SparkSession.builder \
        .appName("AveragePatientScore") \
        .getOrCreate()

    # In a real application, you would pass the path as an argument
    # For this example, we'll hardcode it.
    input_file = "data/observations_micro.json"
    
    calculate_average_score(spark, input_file)

    spark.stop()
