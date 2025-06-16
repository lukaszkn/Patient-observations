import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions._

object AverageScore {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder
      .appName("Average Patient Score")
      .getOrCreate()

    val observationsPath = if (args.length > 0) args(0) else "data/observations_micro.json"

    val observationsDF = spark.read.json(observationsPath)

    val avgScoreDF = observationsDF
      .groupBy("pat_no")
      .agg(avg("total_score").alias("average_score"))

    avgScoreDF.show()

    spark.stop()
  }
}
