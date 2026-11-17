THRESHOLD = .9067876983114506

def acceptance(winner, vector, llm, agree):
    def margin(values):
        return values[winner] - max((v for k,v in values.items() if k != winner), default=0)
    return (.25*vector[winner] + .75*llm[winner] - .02*agree
            + .25*margin(vector) + .05*margin(llm))
