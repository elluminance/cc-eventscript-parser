from typing import Any, Literal
from CCUtils import Character
from enum import Enum
# a class composed of event types in CrossCode.

class ChangeVarType(Enum):
    SET = "set"
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    MOD = "mod"
    OR = "or"
    XOR = "xor"

class RandomChoice:
    def __init__(self, weight: int, activeCondition: str) -> None:
        self.events: list[Event_Step] = []
        self.weight: int = weight
        self.activeCondition: str = activeCondition

class Event_Step:
    def asDict(self) -> dict:
        return {"type": type(self).__name__}

class _ChangeVar(Event_Step):
    def __init__(self, varName: str, value: Any, changeType: ChangeVarType) -> None:
        super().__init__()
        self.varName: str= varName
        self.value: Any = value
        self.changeType: ChangeVarType = changeType

    def asDict(self) -> dict:
        return super().asDict() | {
            "varName": self.varName,
            "value": self.value,
            "changeType": self.changeType.value
        }

class _Message(Event_Step):
    def __init__(self, character: Character, message: str) -> None:
        super().__init__()
        self.character: Character = character
        self.message: str = message
    
    def asDict(self) -> dict:
        return super().asDict() | {
            "message": {
                "en_US": self.message
            },
            "person": self.character.toPersonDict()
        }



class CHANGE_VAR_BOOL(_ChangeVar):
    def __init__(self, varName: str, value: bool, changeType: ChangeVarType = ChangeVarType.SET) -> None:
        super().__init__(varName, value, changeType)

class CHANGE_VAR_NUMBER(_ChangeVar):
    def __init__(self, varName: str, value: int, changeType: ChangeVarType) -> None:
        super().__init__(varName, value, changeType)

class SHOW_SIDE_MSG(_Message):
    def __init__(self, character: Character, message: str) -> None:
        super().__init__(character, message)

class SHOW_MSG(_Message):
    def __init__(self, character: Character, message: str, autoContinue: bool = False) -> None:
        super().__init__(character, message)
        self.autoContinue: bool = autoContinue
    
    def asDict(self) -> dict:
        return super().asDict() | {"autoContinue": self.autoContinue}

class IF(Event_Step):
    def __init__(self, condition: str, *, thenEvent: list[Event_Step] = [], elseEvent: list[Event_Step] = []) -> None:
        super().__init__()
        self.condition: str = condition
        self.thenStep: list[Event_Step] = thenEvent
        self.elseStep: list[Event_Step] = elseEvent
    
    @property
    def withElse(self) -> bool: return len(self.elseStep) > 0

    def asDict(self) -> dict:        
        if self.withElse:
            return super().asDict() | {
                "withElse": self.withElse,
                "condition": self.condition,
                "thenStep": [event.asDict() for event in self.thenStep],
                "elseStep": [event.asDict() for event in self.elseStep]
            }
        else:
            return super().asDict() | {
                "withElse": self.withElse,
                "condition": self.condition,
                "thenStep": [event.asDict() for event in self.thenStep],
            }

class WAIT(Event_Step):
    def __init__(self, time: float, ignoreSlowdown: bool = False) -> None:
        super().__init__()
        self.time: float = float(time)
        self.ignoreSlowdown: bool = ignoreSlowdown

    def asDict(self) -> dict:
        return super().asDict() | {
            "time": self.time,
            "ignoreSlowDown": self.ignoreSlowdown
        }

class ADD_MSG_PERSON(Event_Step):
    def __init__(self, character: Character, side: str, clearSide: bool = False, order: int = 0, customName: str = None) -> None:
        super().__init__()
        self.character: Character = character
        self.side: Literal["LEFT", "RIGHT"] = side
        self.clearSide: bool = clearSide
        self.customName: str = customName
        self.order: int = order

    def asDict(self) -> dict:
        return super().asDict() | {
            "side": self.side,
            "order": self.order,
            "clearSide": self.clearSide,
            "person": self.character.toPersonDict()
        } | {"name": {"en_US": self.customName}} if self.customName is not None else {}

class SELECT_RANDOM(Event_Step):
    def __init__(self) -> None:
        super().__init__()
        self.options: list[RandomChoice] = []

    def asDict(self) -> dict:
        events: dict[list[Event_Step]] = {}

        for i in range(self.options):
          for j in range(self.options[i].events):
            events |= {f"{i}_{j}": [event.asDict() for event in self.options[i].events]}

        return super().asDict() | {
            "options": [
                {
                    "0": " ",
                    "count": len(eventOption.events),
                    "weight": eventOption.weight
                } for eventOption in self.options
            ]
        } | events

class LABEL(Event_Step):
    def __init__(self, labelName: str) -> None:
        super().__init__()
        self.name: str = labelName
    
    def asDict(self) -> dict:
        return super().asDict() | {
            "name": self.name
        }

class GOTO_LABEL(Event_Step): 
    def __init__(self, labelName: str) -> None:
        super().__init__()
        self.name: str = labelName
    
    def asDict(self) -> dict:
        return super().asDict() | {
            "name": self.name
        }

class GOTO_LABEL_WHILE(GOTO_LABEL): 
    def __init__(self, labelName: str, condition: str) -> None:
        super().__init__(labelName)
        self.condition: str = condition
    
    def asDict(self) -> dict:
        return super().asDict() | {
            "name": self.name,
            "condition": self.condition
        }


class CommonEvent:
    def __init__(self, *, type: dict, loopCount: int, frequency: str = "REGULAR", repeat: str = "ONCE", condition: str = "true",  
            eventType: str = "PARALLEL", overrideSideMessage: bool = False, events: dict[int, Event_Step] | list[Event_Step] = {}) -> None:
        self.frequency: str = frequency
        self.repeat: str = repeat
        self.condition: str = condition
        self.eventType: str = eventType
        self.type: dict = type
        self.loopCount: int = loopCount
        self.overrideSideMessage: bool = overrideSideMessage
        self.event: dict[int, Event_Step] = {}
        if events:
            if isinstance(events, list):
                if not all(isinstance(value, Event_Step) for value in events):
                    raise Exception
                for i in range(len(events)):
                    self.event[i+1] = events[i]
            elif isinstance(events, dict):
                if not (all(isinstance(key, int) for key in events.keys()) or \
                all(isinstance(value, Event_Step) for value in events.values())):
                    raise Exception
                else:
                    self.event = events

    @property
    def runOnTrigger(self) -> list[int]:
        return list(self.event.keys())

    def asDict(self):
        return {
            "frequency": self.frequency,
            "repeat": self.repeat,
            "condition": self.condition,
            "eventType": self.eventType,
            "runOnTrigger": self.runOnTrigger,
            "event": [event.asDict() for event in self.event.values()],
            "overrideSideMessage": self.overrideSideMessage,
            "loopCount": self.loopCount,
            "type": self.type
        }