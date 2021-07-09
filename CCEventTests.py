import json
import CCEvents as Events
from CCUtils import Character


def testEvent(input: Events.Event_Step, expectedOutput: dict) -> bool:
    try:
        assert(input.asDict() == expectedOutput)
        print("Test passed!")
        return True
    except AssertionError:
        print("Test failed!")
        print("Expected:")
        print(json.dumps(expectedOutput, indent=2))
        print("Received:")
        print(json.dumps(input.asDict(), indent=2))
        return False

print("Testing SHOW_SIDE_MSG")
event = Events.SHOW_SIDE_MSG(Character("Emilie", "EXHAUSTED"), "Uhm...\\. whoops...")
testEvent(event, 
    {
        "message": {"en_US": "Uhm...\\. whoops..."},
        "type": "SHOW_SIDE_MSG",
        "person": {"person": "main.emilie","expression": "EXHAUSTED"}
    }
)

print("Testing SET_VAR_BOOL")
event = Events.CHANGE_VAR_BOOL("tmp.test", True)
testEvent(event, {
    "changeType": "set",
    "type": "CHANGE_VAR_BOOL",
    "varName": "tmp.test",
    "value": True
})

print("Testing SET_VAR_NUM (with set)")
event = Events.CHANGE_VAR_NUMBER("tmp.test", 3, Events.ChangeVarType.SET)
testEvent(event, 
{
    "changeType": "set",
    "type": "CHANGE_VAR_NUMBER",
    "varName": "tmp.test",
    "value": 3
})

print("Testing SET_VAR_NUM (with add)")
event = Events.CHANGE_VAR_NUMBER("tmp.test", 3, Events.ChangeVarType.ADD)
testEvent(event, 
{
    "changeType": "add",
    "type": "CHANGE_VAR_NUMBER",
    "varName": "tmp.test",
    "value": 3
})

