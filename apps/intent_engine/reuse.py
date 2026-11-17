MODEL = "qwen3.8-max-0902"
THRESHOLD = .92

def acceptance(winner, vector, llm, agree):
    def margin(values):
        return values[winner] - max((v for k,v in values.items() if k != winner), default=0)
    return (.50*vector[winner] + .50*llm[winner]
            + .25*margin(vector) + .05*margin(llm))
