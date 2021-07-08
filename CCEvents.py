from typing import Any
from CCUtils import Character

# a class composed of event types in CrossCode.

class Event_Step:
    def __init__(self, type: str) -> None:
        self._type = type

    @property
    def type(self): return self._type

    def asDict(self) -> dict:
        return {"type": self.type}

class _ChangeVar(Event_Step):
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

class _Message(Event_Step):
    def __init__(self, type: str, character: Character, message: str) -> None:
        super().__init__(type)
        self.character = character
        self.message = message
    
    def asDict(self) -> dict:
        return super().asDict() | {
            "message": {
                "en_US": self.message
            },
            "person": self.character.toPersonDict()
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
    def __init__(self, character: Character, message: str) -> None:
        super().__init__("SHOW_SIDE_MSG", character, message)

class SHOW_MSG(_Message):
    def __init__(self, character: Character, message: str, autoContinue: bool = False) -> None:
        super().__init__("SHOW_MSG", character, message)
        self.autoContinue = autoContinue
    
    def asDict(self) -> dict:
        return super().asDict() | {"autoContinue": self.autoContinue}

class IF(Event_Step):
    def __init__(self, condition: str, *, thenEvent: list[Event_Step] = [], elseEvent: list[Event_Step] = []) -> None:
        super().__init__(type = "IF")
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
        super().__init__("WAIT")
        self.time = float(time)
        self.ignoreSlowdown = ignoreSlowdown

    def asDict(self) -> dict:
        return super().asDict() | {
            "time": self.time,
            "ignoreSlowDown": self.ignoreSlowdown
        }

class ADD_MSG_PERSON(Event_Step):
    def __init__(self, character: Character, side: str, clearSide: bool = False, order: int = 0, customName: str = None) -> None:
        super().__init__("ADD_MSG_PERSON")
        self.character = character
        self.side = side
        self.clearSide = clearSide
        self.customName = customName
        self.order = order

    @property
    def side(self):
        return self._side

    @side.setter
    def side(self, value):
        if value in ["LEFT", "RIGHT"]:
            self._side = value
        else:
            raise ValueError(f"Invalid side '{value}'")

    def asDict(self) -> dict:
        return super().asDict() | {
            "side": self.side,
            "order": self.order,
            "clearSide": self.clearSide,
            "person": self.character.toPersonDict()
        } | {"name": {"en_US": self.customName}} if self.customName is not None else {}

class SELECT_RANDOM(Event_Step):
    class RandomChoice:
        def __init__(self, weight: int, activeCondition: str) -> None:
            self.events: list[Event_Step] = []
            self.weight: int = weight
            self.activeCondition: str = activeCondition

    def __init__(self) -> None:
        super().__init__(type = "SELECT_RANDOM")
        self.options: list[SELECT_RANDOM.RandomChoice] = []

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