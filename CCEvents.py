from typing import Any
# a class composed of event types in CrossCode.

class Event:
    def __init__(self, type: str) -> None:
        self._type = type

    @property
    def type(self): return self._type

    def asDict(self) -> dict:
        return {"type": self.type}

class _ChangeVar(Event):
    def __init__(self, type: str, varName: str, value: Any, changeType: str) -> None:
        super().__init__(type),
        self.varName = varName
        self.value = value
        self.changeType = changeType
    

    @property
    def changeType(self):
        return self._changeType

    @changeType.setter
    def changeType(self, value):
        if value not in ["set", "add"]:
            raise Exception(f"Invalid changeType '{value}'")
        self._changeType = value

    def asDict(self) -> dict:
        return super().asDict() | {
            "varName": self.varName,
            "value": self.value,
            "changeType": self.changeType
        }

class _Message(Event):
    def __init__(self, type: str, character: str, expression: str, message: str) -> None:
        super().__init__(type)
        self.character = character
        self.expression = expression
        self.message = message
    
    def asDict(self) -> dict:
        return super().asDict() | {
            "message": {
                "en_US": self.message
            },
            "person": {
                "person": self.character,
                "expression": self.expression
            }
        }

class CHANGE_VAR_BOOL(_ChangeVar):
    def __init__(self, varName: str, value: bool) -> None:
        super().__init__("CHANGE_VAR_BOOL", varName, value, "set")
    
    def asDict(self) -> dict:
        return super().asDict()

class CHANGE_VAR_NUMBER(_ChangeVar):
    def __init__(self, varName: str, value: int, changeType: str) -> None:
        super().__init__("CHANGE_VAR_NUMBER", varName, value, changeType)

class SHOW_SIDE_MSG(_Message):
    def __init__(self, character: str, expression: str, message: str) -> None:
        super().__init__("SHOW_SIDE_MSG", character, expression, message)

class SHOW_MSG(_Message):
    def __init__(self, character: str, expression: str, message: str, autoContinue: bool = False) -> None:
        super().__init__("SHOW_MSG", character, expression, message)
        self.autoContinue = autoContinue
    
    def asDict(self) -> dict:
        return super().asDict() | {"autoContinue": self.autoContinue}

class IF(Event):
    def __init__(self, condition: str, *, thenEvent: list[Event] = [], elseEvent: list[Event] = []) -> None:
        super().__init__(type = "IF")
        self.condition: str = condition
        self.thenStep: list[Event] = thenEvent
        self.elseStep: list[Event] = elseEvent
    
    @property
    def withElse(self) -> bool: return len(self.elseEvent) > 0

    def asDict(self) -> dict:
        thenStepList: list[dict] = []
        elseStepList: list[dict] = []
        for event in self.thenStep: thenStepList.append(event.asDict())
        
        if self.withElse:
            for event in self.elseStep: elseStepList.append(event.asDict())
            return super().asDict() | {
                "withElse": self.withElse,
                "condition": self.condition,
                "thenStep": self.thenStep,
                "elseStep": self.elseStep
            }
        else:
            return super().asDict() | {
                "withElse": self.withElse,
                "condition": self.condition,
                "thenStep": self.thenStep,
            }
