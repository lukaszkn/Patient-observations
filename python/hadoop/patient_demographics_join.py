from mrjob.job import MRJob
from mrjob.step import MRStep
import json

class MRAvgBPM(MRJob):
    def mapper(self, _, line):
        try:
            data = json.loads(line)
            if 'readings' in data:
                # It's an observation record
                for reading in data['readings']:
                    if reading['type'] == 'heart_rate':
                        yield data['pat_no'], {'sum': reading['value'], 'count': 1}
            else:
                # It's a patient record, pass it through
                yield data['pat_no'], {'name': data['name']}
        except (json.JSONDecodeError, KeyError):
            pass

    def reducer(self, key, values):
        total_bpm = 0
        count = 0
        name = None
        for value in values:
            if 'sum' in value:
                total_bpm += value['sum']
                count += value['count']
            elif 'name' in value:
                name = value['name']
        
        if name and count > 0:
            yield name, total_bpm / count

if __name__ == '__main__':
    MRAvgBPM.run()
