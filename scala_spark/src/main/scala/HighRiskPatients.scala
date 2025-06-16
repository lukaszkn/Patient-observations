import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions._

object HighRiskPatients {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder
      .appName("High Risk Patients")
      .getOrCreate()

    val observationsPath = if (args.length > 0) args(0) else "data/observations_micro.json"
    val riskThreshold = if (args.length > 1) args(1).toDouble else 5.0

    val observationsDF = spark.read.json(observationsPath)

    val avgScoreDF = observationsDF
      .groupBy("pat_no")
      .agg(avg("total_score").alias("average_score"))

    val highRiskDF = avgScoreDF.filter(col("average_score") > riskThreshold)

    highRiskDF.show()

    spark.stop()
  }
}
