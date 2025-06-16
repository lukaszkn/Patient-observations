from mrjob.job import MRJob
from mrjob.step import MRStep
import json

class MRHighRiskPatients(MRJob):

    def configure_args(self):
        super(MRHighRiskPatients, self).configure_args()
        self.add_passthru_arg('--risk-threshold', type=float, default=5.0, help='Threshold for average score to be considered high risk.')

    def steps(self):
        return [
            MRStep(mapper=self.mapper_get_scores,
                   reducer=self.reducer_avg_scores),
            MRStep(mapper=self.mapper_filter_high_risk)
        ]

    def mapper_get_scores(self, _, line):
        try:
            data = json.loads(line)
            pat_no = data.get('pat_no')
            total_score = data.get('total_score')
            if pat_no and total_score is not None:
                yield pat_no, total_score
        except json.JSONDecodeError:
            pass

    def reducer_avg_scores(self, key, values):
        scores = list(values)
        avg_score = sum(scores) / len(scores)
        yield key, avg_score

    def mapper_filter_high_risk(self, pat_no, avg_score):
        if avg_score > self.options.risk_threshold:
            yield pat_no, avg_score

if __name__ == '__main__':
    MRHighRiskPatients.run()
