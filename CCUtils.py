
class Character:
    characterLookup: dict = {
        'lea': 'main.lea',
        'emilie': 'main.emilie',
        'c\'tron': 'main.glasses',
        'apollo': 'antagonists.fancyguy',
        'joern': 'antagonists.sidekick',
        'shizuka': 'main.shizuka',
        'lukas': 'main.schneider',
        'schneider': 'main.schneider',
        'luke': 'main.luke',
        'sergey': 'main.sergey',
        'sergey (avatar)': 'main.sergey-av',
        'beowulf': 'main.grumpy',
        'buggy': 'main.buggy',
        'hlin': 'main.guild-leader'
    }

    def __init__(self, name: str, expression: str, internalName: str = None) -> None:
        self.name = name
        self.expression = expression
        if internalName is None:
            self.internalName = Character.characterLookup[self.name.strip().lower()]
        else:
            self.internalName = internalName