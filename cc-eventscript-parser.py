import json
import os
import re
import sys
from typing import Union, Any

# ~ crosscode eventscript v1.4.0 parser, by EL ~
# to run:
#   python cc-eventscript-parser.py <input text file>
#
# to make a text file:
#   see readme

debug = True

# a handy dictionary for converting a character's readable name to their internal name.
# it's simple enough to add more characters (or even custom characters!) to this.
# just add a new key of the "readable" name (in lowercase), and the corresponding internal name.
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

class CCEventRegex:
    # matches lines that start with "#" or "//"
    comment = re.compile(r"^(?:#|\/\/).*")
    # matches strings of the form "import (fileName)"
    importFile = re.compile(r"^import\s+(?:(?:\.\/)?patches\/)?(?P<directory>(?:[.\w]+[\\\/])*)(?P<filename>[\w+-]+){1}?(?:\.json)?$", flags=re.I)
    filepath = re.compile(r"^(?P<directory>(?:[.\w]+[\\\/])*)(?P<filename>\S+.json)$")
    # matches strings of the form "(character) > (expression): (message)" or "(character) > (expression) (message)"
    dialogue = re.compile(r"(?P<character>.+)\s*>\s*(?P<expression>[A-Z_]+)[\s:](?P<dialogue>.+)$")
    # matches strings of the form "message (number)", insensitive search
    eventHeader = re.compile(r"^(?:message|event) (?P<eventNum>\d+):?$", flags=re.I)
    # matches strings of the form "== title =="
    title = re.compile(r"^== (?P<eventTitle>.+) ==$")
    # matches strings of the form "(key): (value)"
    property = re.compile(r"^(?P<property>\w+)\s*:\s*(?P<value>.+)$")
    # matches "set (varname) (true/false)"
    setVarBool = re.compile(r"^set\s+(?P<varName>[\w\.]+)\s*=\s*(?P<value>true|false)$", flags=re.I)
    # matches "set (varname) (+/-/=) (number)"
    setVarNum = re.compile(r"^set\s+(?P<varName>[\w\.]+)\s*(?P<operation>=|\+|-)\s*(?P<value>\d+)$", flags=re.I)

    # matches "if (condition)", "else", and  "endif" respectively
    ifStatement = re.compile(r"^if (?P<condition>.+)$")
    elseStatement = re.compile(r"^else$")
    endifStatement = re.compile(r"^endif$")

class EventItem:
    eventTypes = ["import", "standard"]

    def __init__(self, eventType: str, filePath: str, event: Union[list[dict], None] = None) -> None:
        if eventType.lower() not in EventItem.eventTypes: raise Exception(f"Error: EventType {eventType} not valid!")
        self.type = eventType.lower()
        if not re.match(CCEventRegex.filepath, filePath): raise Exception(f"Error: Invalid file path {filePath}!")
        self.filepath = filePath
        self.event = event

class EventGenerators:
    @staticmethod
    def ifStatement(condition: str) -> dict: return {"withElse": False, "type": "IF", "condition": condition, "thenStep": []}

    @staticmethod
    def messageSet(num: int) -> dict: return EventGenerators.ifStatement(f"call.runCount == {num}")

    @staticmethod
    def changeBoolValue(variable: str, value: bool) -> dict:
        if type(value) is not bool: raise Exception(f"Invalid value '{value}', must be boolean")
        return {"changeType": "set","type": "CHANGE_VAR_BOOL","varName": variable, "value": value}

    @staticmethod
    def changeNumValue(variable: str, changeType: str, value: int) -> dict: 
        if changeType not in ["set", "add"]: raise Exception(f"Error: Invalid changeType '{changeType}'")
        if type(value) is not int: raise Exception(f"Invalid value '{value}', must be integer")
        return {"changeType": changeType, "type": "CHANGE_VAR_NUMBER", "varName": variable, "value": value}

    @staticmethod
    def baseEvent(): 
        return {
            "frequency": "REGULAR",
            "repeat": "ONCE",
            "condition": "true",
            "eventType": "PARALLEL",
            "runOnTrigger": [],
            "event": [],
            "overrideSideMessage": False,
            "loopCount": 3,
            "type": {
                "killCount": 0,
                "type": "BATTLE_OVER"
            }
        }

def processDialogue(inputString: str) -> dict:
    messageMatch = re.match(CCEventRegex.dialogue, inputString)
    readableCharName, expression, message = messageMatch.group("character", "expression", "dialogue")
    charName: str = characterLookup[readableCharName.strip().lower()]

    messageEvent = {
        "message": {
            "en_US": message.strip()
        },
        "type": "SHOW_SIDE_MSG",
        "person": {
            "person": charName,
            "expression": expression.strip()
        }
    }
    return messageEvent

def processEvents(eventStrs: list[str], isIf: bool = False) -> list[dict]:
    workingList: list[dict] = []
    ifCount: int = 0
    ifCondition: str = ""
    buffer = []
    ifEventList = []
    hasElse = False

    for line in eventStrs:
        line = line.strip()
        if match := re.match(CCEventRegex.ifStatement, line):
            if ifCount == 0:
                ifCondition = match.group("condition")
            else:
                buffer.append(line)
            ifCount += 1

        elif re.match(CCEventRegex.endifStatement, line):
            if ifCount > 1:
                buffer.append(line)
                ifCount -= 1
            elif ifCount < 1:
                raise Exception("Error: 'endif' found outside of if block")
            else:
                ifBlock = EventGenerators.ifStatement(ifCondition)
                ifBlock["thenStep"], ifBlock["elseStep"] = processEvents(buffer, True)
                if ifBlock["elseStep"] is not None: ifBlock["withElse"] = True
                else: del ifBlock["elseStep"]
                ifCount = 0
                workingList.append(ifBlock)

        # adds to string buffer for later processing
        elif ifCount > 0:
            buffer.append(line)

        elif re.match(CCEventRegex.elseStatement, line):
            if (not isIf):
                raise Exception("Error: 'else' statement found outside of if block.")
            elif hasElse:
                raise Exception("Error: Multiple 'else' statements found inside of if block.")
            else:
                hasElse = True
                ifEventList = workingList.copy()
                workingList = []

        elif match := re.match(CCEventRegex.dialogue, line):
            workingList.append(processDialogue(line))

        elif match := re.match(CCEventRegex.setVarBool, line):
            varName, value = match.group("varName", "value")
            workingList.append(EventGenerators.changeBoolValue(varName, bool(value)))

        elif match := re.match(CCEventRegex.setVarNum, line):
            varName, sign, number = match.group("varName", "operation", "value")
            if sign == "=":
                newEvent = EventGenerators.changeNumValue(varName, "set", int(number))
            elif sign in ["+", "-"]:
                newEvent = EventGenerators.changeNumValue(varName, "add", int(f"{sign}{number}"))
            workingList.append(newEvent)

    if ifCount > 0:
        raise Exception("'if' found without corresponding 'endif'")

    if isIf: 
        if not hasElse:
            return workingList, None
        else:
            return ifEventList, workingList

    return workingList


def handleEvent(eventStrs: list[str]) -> dict:
    event = EventGenerators.baseEvent()
    
    messageNumber = 0
    buffer = []
    trackMessages = False

    for line in eventStrs:
        line = line.strip()
        # skip blank lines and comments
        if (not line) or re.match(CCEventRegex.comment, line): continue

        if match := re.match(CCEventRegex.eventHeader, line):
            if trackMessages:
                workingEvent["thenStep"] = processEvents(buffer)
                event["event"].append(workingEvent)
                buffer = []

            messageNumber += 1
            workingEvent = EventGenerators.messageSet(messageNumber)
            trackMessages = True
            event["runOnTrigger"].append(int(match.group("eventNum")))

        elif trackMessages:
            buffer.append(line) 

        elif match := re.match(CCEventRegex.property, line):
            propertyName, value = match.group("property", "value")
            if propertyName in ["frequency", "repeat", "condition", "eventType", "loopCount"]:
                event[propertyName] = value
            else: 
                print(f"Unrecognized property \"{propertyName}\", skipping...", file = sys.stderr)

        else:
            print(f"Unrecognized line \"{line}\", ignoring...", file = sys.stderr)
        
    #workingEvent = EventGenerators.messageSet(messageNumber)
    workingEvent["thenStep"] = processEvents(buffer)
    event["event"].append(workingEvent)

    return event

def readFile(inputFilename: str) -> dict[str, dict]:
    eventDict: dict = {}
    currentEvent: str = ""
    buffer: list[str] = []
    with open(inputFilename, "r") as inputFile:
        for line in inputFile:
            if re.match(CCEventRegex.comment, line): continue
            
            if match := re.match(CCEventRegex.importFile, line):
                filename = f"./patches/{match.group('directory')}{match.group('filename')}.json"
                eventDict[match.group("filename")] = EventItem("import", filename)

            elif match := re.match(CCEventRegex.title, line):
                if currentEvent != "": # check that the event isn't empty so it only runs if there's actually something there
                    eventDict[currentEvent].event = handleEvent(buffer)
                # set the current event and clear the buffer
                currentEvent = match.group("eventTitle").replace("/",".")
                filename = f"./patches/{currentEvent}.json"
                if currentEvent in eventDict:
                    raise KeyError("Duplicate event name found in input file.")
                eventDict[currentEvent] = EventItem("standard", filename, None)
                buffer = []
            else:
                buffer.append(line)
        eventDict[currentEvent].event = handleEvent(buffer)
    
    return eventDict

def generatePatchFile(events: dict) -> list[dict]:
    patchDict: list[dict] = []
    patchDict.append({"type": "ENTER", "index": "commonEvents"})
    for event in events.values():
        if event.type in ["import", "standard"]:
            fixedFilename = re.sub(r"^(\.\/)","mod:",event.filepath)
            if debug: print(f"DEBUG: Writing patch for file at '{fixedFilename}'.")
            patchDict.append(
                {
                    "type": "IMPORT",
                    "src": fixedFilename
                }
            ),
    patchDict.append({"type": "EXIT"})
    return patchDict

def writeEventFiles(events: dict) -> None:
    os.makedirs("./patches/", exist_ok = True)
    for eventName, eventInfo in events.items():
        filename = eventInfo.filepath
        directoryMatch = re.match(CCEventRegex.filepath, filename)
        if directoryMatch and directoryMatch.group("directory"): os.makedirs(directoryMatch.group("directory"), exist_ok= True)
        if eventInfo.type == "standard":
            if debug: print(f"DEBUG: Writing file '{filename}'.")
            with open(filename, "w+") as jsonFile:
                json.dump({eventName: eventInfo.event}, jsonFile, indent = 2 if debug else None)
        elif eventInfo.type == "import":
            if(not os.path.exists(filename)):
                print(f"Warning: File {filename} not found for importing! Adding, but make sure to create the file before using the patch.")

def writeDatabasePatchfile(patchDict: dict) -> None:
    os.makedirs("./assets/data/", exist_ok = True)
    
    with open("./assets/data/database.json.patch", "w+") as patchFile:
        json.dump(patchDict, patchFile, indent = 2 if debug else None)


if __name__ == "__main__":
    inputFilename = sys.argv[1]
    events = readFile(inputFilename)
    eventFiles = writeEventFiles(events)
    writeDatabasePatchfile(generatePatchFile(events))
