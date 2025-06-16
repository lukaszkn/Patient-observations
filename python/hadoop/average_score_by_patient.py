from mrjob.job import MRJob
from mrjob.step import MRStep
import json

class MRAverageScoreByPatient(MRJob):

    def steps(self):
        return [
            MRStep(mapper=self.mapper_get_scores,
                   reducer=self.reducer_avg_scores)
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
        yield key, sum(scores) / len(scores)

if __name__ == '__main__':
    MRAverageScoreByPatient.run()
