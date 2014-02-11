# Define the most important crawlers
crawlers = (
    'crawler',

    'google',

    'yahoo',
    'slurp',
    'scooter',

    'msnbot',

    'alexa',

    'abacho',

    'jeeves',

    'lycos',

    'yandex',
    'yadirect',
)

def is_crawler(agent):
    agent = agent.lower()
    for crawler in crawlers:
        if crawler in agent:
            return True
    return False
