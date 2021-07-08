class Character:
    @staticmethod
    def characterLookup(charName: str) -> str:
        match charName.lower():
            case 'lea': return 'main.lea'
            case 'emilie' | "emilinator": return 'main.emilie'
            case 'c\'tron': return 'main.glasses'
            case 'apollo': return 'antagonists.fancyguy'
            case 'joern': return 'antagonists.sidekick'
            case 'shizuka': return 'main.shizuka'
            case 'lukas' | 'schneider': return 'main.schneider'
            case 'luke': return 'main.luke'
            case 'sergey': return 'main.sergey'
            case 'sergey (avatar)': return 'main.sergey-av'
            case 'beowulf': return 'main.grumpy'
            case 'buggy': return 'main.buggy'
            case 'hlin': return 'main.guild-leader'
            case _: return charName

    def __init__(self, name: str, expression: str, internalName: str = None) -> None:
        self.name: str = name
        self.expression: str = expression
        if internalName is None:
            self.internalName: str = Character.characterLookup(self.name.strip().lower())
        else:
            self.internalName: str = internalName
    
    def toPersonDict(self) -> dict:
        return {
            "person": self.internalName,
            "expression": self.expression
        }