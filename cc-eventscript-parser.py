import json
import os
import re
import sys
from typing import Union

# ~ crosscode eventscript v1.3.1 parser, by EL ~
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

class EventItem:
    eventTypes = ["import", "standard"]

    def __init__(this, eventType: str, filePath: str, event: Union[list[dict], None] = None) -> None:
        if eventType.lower() not in EventItem.eventTypes: raise Exception(f"Error: EventType {eventType} not valid!")
        this.type = eventType.lower()
        if not re.match(pathFileRegex, filePath): raise Exception(f"Error: Invalid file path {filePath}!")
        this.filepath = filePath
        this.event = event


#region regex

# matches lines that start with "#" or "//"
commentRegex = re.compile(r"^(?:#|\/\/).*")
# matches strings of the form "import (fileName)"
importRegex = re.compile(r"^import\s+(?:(?:\.\/)?patches\/)?(?P<directory>(?:[.\w]+[\\\/])*)(?P<filename>[\w+-]+){1}?(?:\.json)?$", flags=re.I)
pathFileRegex = re.compile(r"^(?P<directory>(?:[.\w]+[\\\/])*)(?P<filename>\S+.json)$")
# matches strings of the form "(character) > (expression): (message)" or "(character) > (expression) (message)"
dialogueRegex = re.compile(r"(?P<character>.+)\s*>\s*(?P<expression>[A-Z_]+)[\s:](?P<dialogue>.+)$")
# matches strings of the form "message (number)", insensitive search
messageRegex = re.compile(r"^(?:message|event) (?P<messageNum>\d+):?$", flags=re.I)
# matches strings of the form "== title =="
titleRegex = re.compile(r"^== (?P<eventTitle>.+) ==$")
# matches strings of the form "(key): (value)"
propertyRegex = re.compile(r"^(?P<property>\w+)\s*:\s*(?P<value>.+)$")
# matches "set (varname) (true/false)"
setVarBoolRegex = re.compile(r"^set\s+(?P<varName>[\w\.]+)\s*=\s*(?P<value>true|false)$", flags=re.I)
# matches "set (varname) (+/-/=) (number)"
setVarNumRegex = re.compile(r"^set\s+(?P<varName>[\w\.]+)\s*(?P<operation>=|\+|-)\s*(?P<value>\d+)$", flags=re.I)

# matches "if (condition)", "else", and  "endif" respectively
ifRegex = re.compile(r"^if (?P<condition>.+)$")
elseRegex = re.compile(r"^else$")
endifRegex = re.compile(r"^endif$")
#endregion regex

genIfSkeleton = lambda condition: {"withElse": False, "type": "IF", "condition": condition, "thenStep": []}
genMessageSetSkeleton = lambda num: genIfSkeleton(f"call.runCount == {num}")
genChangeBoolSkeleton = lambda var, value: {"changeType": "set","type": "CHANGE_VAR_BOOL","varName": var, "value": value}
genChangeNumSkeleton = lambda var, type, value: {"changeType": type,"type": "CHANGE_VAR_BOOL","varName": var, "value": value}


def processDialogue(inputString: str) -> dict:
    messageMatch = re.match(dialogueRegex, inputString)
    readableCharName, expression, message = messageMatch.groups()
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

def handleEvent(eventStr: str) -> dict:

    def processEvents(eventStr: str, isIf: bool = False) -> list[dict]:
        workingList: list[dict] = []
        ifCount: int = 0
        ifCondition: str = ""
        stringBuffer: str = ""
        ifEventList = []
        hasElse = False

        for line in eventStr.splitlines():
            line = line.strip()
            if match := re.match(ifRegex, line):
                if ifCount == 0:
                    ifCondition = match.group(1)
                else:
                    stringBuffer += line + "\n"
                ifCount += 1

            elif re.match(endifRegex, line):
                if ifCount > 1:
                    stringBuffer += line + "\n"
                    ifCount -= 1
                elif ifCount < 1:
                    raise Exception("Error: 'endif' found outside of if block")
                else:
                    ifBlock = genIfSkeleton(ifCondition)
                    ifBlock["thenStep"], ifBlock["elseStep"] = processEvents(stringBuffer, True)
                    if ifBlock["elseStep"] is not None: ifBlock["withElse"] = True
                    else: del ifBlock["elseStep"]
                    ifCount = 0
                    workingList.append(ifBlock)

            # adds to string buffer for later processing
            elif ifCount > 0:
                stringBuffer += line + "\n"

            elif re.match(elseRegex, line):
                if (not isIf):
                    raise Exception("Error: 'else' statement found outside of if block.")
                elif hasElse:
                    raise Exception("Error: Multiple 'else' statements found inside of if block.")
                else:
                    hasElse = True
                    ifEventList = workingList.copy()
                    workingList = []

            elif match := re.match(dialogueRegex, line):
                workingList.append(processDialogue(line))

            elif match := re.match(setVarBoolRegex, line):
                workingList.append(genChangeBoolSkeleton(match.group(1),bool(match.group(2))))

            elif match := re.match(setVarNumRegex, line):
                varName, sign, number = match.groups()
                if sign == "=":
                    newEvent = genChangeNumSkeleton(varName, "set", int(number))
                elif sign in ["+", "-"]:
                    newEvent = genChangeNumSkeleton(varName, "add", int(f"{sign}{number}"))
                workingList.append(newEvent)

        if ifCount > 0:
            raise Exception("'if' found without corresponding 'endif'")

        if isIf: 
            if not hasElse:
                return workingList, None
            else:
                return ifEventList, workingList

        return workingList

    event = {
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
    
    messageNumber = 0
    stringBuffer = ""
    trackMessages = False

    for line in eventStr.splitlines():
        line = line.strip()
        # skip blank lines and comments
        if (not line) or re.match(commentRegex, line): continue

        if match := re.match(messageRegex, line):
            if trackMessages:
                workingEvent = genMessageSetSkeleton(messageNumber)
                workingEvent["thenStep"] = processEvents(stringBuffer)
                event["event"].append(workingEvent)
                stringBuffer = ""

            messageNumber += 1
            trackMessages = True
            event["runOnTrigger"].append(int(match.group(1)))

        elif trackMessages:
            stringBuffer += line + "\n"

        elif match := re.match(propertyRegex, line):
            propertyName, value = match.groups()
            if propertyName in ["frequency", "repeat", "condition", "eventType", "loopCount"]:
                event[propertyName] = value
            else: 
                print(f"Unrecognized property \"{propertyName}\", skipping...", file = sys.stderr)

        else:
            print(f"Unrecognized line \"{line}\", ignoring...", file = sys.stderr)
        
    workingEvent = genMessageSetSkeleton(messageNumber)
    workingEvent["thenStep"] = processEvents(stringBuffer)
    event["event"].append(workingEvent)

    return event

def readFile(inputFilename: str) -> dict[str, dict]:
    eventDict: dict = {}
    currentEvent: str = ""
    bufferString = ""
    with open(inputFilename, "r") as inputFile:
        for line in inputFile:
            if re.match(commentRegex, line): continue
            
            if match := re.match(importRegex, line):
                filename = f"./patches/{match.group('directory')}{match.group('filename')}.json"
                eventDict[match.group("filename")] = EventItem("import", filename)

            elif match := re.match(titleRegex, line):
                if currentEvent != "": # check that the event isn't empty so it only runs if there's actually something there
                    eventDict[currentEvent].event = handleEvent(bufferString)
                # set the current event and clear the buffer
                currentEvent = match.group(1).replace("/",".")
                filename = f"./patches/{currentEvent}.json"
                if currentEvent in eventDict:
                    raise KeyError("Duplicate event name found in input file.")
                eventDict[currentEvent] = EventItem("standard", filename, None)
                bufferString = ""
            else:
                bufferString += line + "\n"
        eventDict[currentEvent].event = handleEvent(bufferString)
    
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
        directoryMatch = re.match(pathFileRegex, filename)
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
