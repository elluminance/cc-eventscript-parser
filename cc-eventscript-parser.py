import json
import os
import re
import sys
import CCEvents as Events
from typing import Union, Any

# ~ crosscode eventscript v1.4.0 parser, by EL ~
# to run:
#   python cc-eventscript-parser.py <input text file>
#
# to make a text file:
#   see readme

debug = False

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
    comment = re.compile(r"(?<!\\)(?:#|\/\/).*")
    # matches strings of the form "import (fileName)"
    importFile = re.compile(r"^import\s+(?:(?:\.\/)?patches\/)?(?P<directory>(?:[.\w]+[\\\/])*)(?P<filename>[\w+-]+){1}?(?:\.json)?$", flags=re.I)
    filepath = re.compile(r"^(?P<directory>(?:[.\w]+[\\\/])*)(?P<filename>\S+.json)$")
    # matches strings of the form "(character) > (expression): (message)" or "(character) > (expression) (message)"
    dialogue = re.compile(r"^(?P<character>.+)\s*>\s*(?P<expression>[A-Z_]+)[\s:](?P<dialogue>.+)$")
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

    def __init__(self, eventType: str, filePath: str, event: Union[Events.CommonEvent, None] = None) -> None:
        if eventType.lower() not in EventItem.eventTypes: raise Exception(f"Error: EventType {eventType} not valid!")
        self.type = eventType.lower()
        if not re.match(CCEventRegex.filepath, filePath): raise Exception(f"Error: Invalid file path {filePath}!")
        self.filepath = filePath
        self.event = event





def processDialogue(inputString: str) -> Events.SHOW_SIDE_MSG:
    messageMatch = re.match(CCEventRegex.dialogue, inputString)
    readableCharName, expression, message = messageMatch.group("character", "expression", "dialogue")
    charName: str = characterLookup[readableCharName.strip().lower()]

    messageEvent = Events.SHOW_SIDE_MSG(charName, expression, message)
    return messageEvent


def processEvents(eventStrs: list[str]) -> list[Events.Event_Step]:
    workingEvent: list[Events.Event_Step] = []
    ifCount: int = 0
    inIf = False
    buffer = []
    hasElse = False

    for line in eventStrs:
        line = line.strip()
        
        # if (condition)
        if match := re.match(CCEventRegex.ifStatement, line):
            if not inIf:
                ifEvent = Events.IF(match.group("condition"))
                inIf = True
            else:
                buffer.append(line)
            ifCount += 1

        # endif
        elif re.match(CCEventRegex.endifStatement, line):
            # only count the last "endif" of a block
            if ifCount > 1:
                buffer.append(line)
                ifCount -= 1
            # make sure that there is no excess endifs
            elif ifCount < 1:
                raise Exception("Error: 'endif' found outside of if block")
            # process if statement for the corresponding if
            else:
                if hasElse: ifEvent.elseStep = processEvents(buffer)
                else: ifEvent.thenStep = processEvents(buffer)
                ifCount = 0
                workingEvent.append(ifEvent)
                inIf = False
                buffer = []

        # else
        elif re.match(CCEventRegex.elseStatement, line):
            if (not inIf):
                raise Exception("Error: 'else' statement found outside of if block.")
            elif hasElse:
                raise Exception("Error: Multiple 'else' statements found inside of if block.")
            elif ifCount > 1:
                buffer.append(line)
            else:
                hasElse = True
                ifEvent.thenStep = processEvents(buffer)
                buffer = []

        # adds to string buffer for later processing
        elif inIf:
            buffer.append(line)

        # dialogue
        elif match := re.match(CCEventRegex.dialogue, line):
            workingEvent.append(processDialogue(line))

        # set var = bool
        elif match := re.match(CCEventRegex.setVarBool, line):
            varName, value = match.group("varName", "value")
            workingEvent.append(Events.CHANGE_VAR_BOOL(varName, bool(value)))

        # set var +|-|= num
        elif match := re.match(CCEventRegex.setVarNum, line):
            varName, sign, number = match.group("varName", "operation", "value")
            if sign == "=":
                workingEvent.append(Events.CHANGE_VAR_NUMBER(varName, int(number), "set"))
            elif sign in ["+", "-"]:
                workingEvent.append(Events.CHANGE_VAR_NUMBER(varName, int(f"{sign}{number}"), "add"))

    #ensure that ifs are properly terminated
    if inIf:
        raise Exception("'if' found without corresponding 'endif'")

    return workingEvent


def handleEvent(eventStrs: list[str]) -> Events.CommonEvent:
    event = Events.CommonEvent(type={"killCount": 0, "type": "BATTLE_OVER"}, loopCount = 3)

    print(event.asDict())
    eventNumber: int = 0
    buffer: list[str] = []
    trackMessages: bool = False

    for line in eventStrs:
        if match := re.match(CCEventRegex.eventHeader, line):
            if trackMessages:
                workingEvent.thenStep = processEvents(buffer)
                event.event[eventNumber] = workingEvent
                buffer = []

            eventNumber += 1
            workingEvent = Events.IF(f"call.runCount == {eventNumber}")
            trackMessages = True

        elif trackMessages:
            buffer.append(line) 

        elif match := re.match(CCEventRegex.property, line):
            propertyName, value = match.group("property", "value")
            propertyName = propertyName.lower()
            
            if propertyName == "frequency": event.frequency = value
            elif propertyName == "repeat": event.repeat = value
            elif propertyName == "condition": event.condition = value
            elif propertyName == "eventtype": event.eventType = value
            elif propertyName == "loopcount": event.loopCount = int(value)
            else: print(f"Unrecognized property \"{propertyName}\", skipping...", file = sys.stderr)

        else:
            print(f"Unrecognized line \"{line}\", ignoring...", file = sys.stderr)
    workingEvent.thenStep = processEvents(buffer)
    event.event[eventNumber] = workingEvent

    return event

def readFile(inputFilename: str) -> dict[str, EventItem]:
    eventDict: dict[str, EventItem] = {}
    eventTitle: str = ""
    buffer: list[str] = []
    with open(inputFilename, "r") as inputFile:
        for line in inputFile:
            # remove comments and strip excess whitespace
            line = re.sub(CCEventRegex.comment, "", line).strip()

            # skip blank lines
            if (not line): continue
            
            # handle file imports
            if match := re.match(CCEventRegex.importFile, line):
                filename = f"./patches/{match.group('directory')}{match.group('filename')}.json"
                eventTitle = match.group("filename")
                if eventTitle in eventDict: raise KeyError(f"Duplicate event name '{eventTitle}' found in input file.")
                eventDict[eventTitle] = EventItem("import", filename)
                eventTitle = ""

            elif match := re.match(CCEventRegex.title, line):
                # check that the event isn't empty so it only runs if there's actually something there
                if buffer: 
                    eventDict[eventTitle].event = handleEvent(buffer)
                    eventTitle = ""

                # set the current event and clear the buffer
                eventTitle = match.group("eventTitle").replace("/",".")
                filename = f"./patches/{eventTitle}.json"
                
                if eventTitle in eventDict: raise KeyError("Duplicate event name found in input file.")
                eventDict[eventTitle] = EventItem("standard", filename, None)
                buffer = []

            # add anything missing to buffer
            else:
                buffer.append(line)

        # process any final events if one is present
        if buffer: eventDict[eventTitle].event = handleEvent(buffer)
    
    return eventDict

def generatePatchFile(events: dict[str, EventItem]) -> list[dict]:
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

def writeEventFiles(events: dict[str, EventItem]) -> None:
    os.makedirs("./patches/", exist_ok = True)
    for eventName, eventInfo in events.items():
        filename = eventInfo.filepath
        directoryMatch = re.match(CCEventRegex.filepath, filename)
        if directoryMatch and directoryMatch.group("directory"): os.makedirs(directoryMatch.group("directory"), exist_ok= True)
        if eventInfo.type == "standard":
            if debug: print(f"DEBUG: Writing file '{filename}'.")
            with open(filename, "w+") as jsonFile:
                json.dump({eventName: eventInfo.event.asDict()}, jsonFile, indent = 2 if debug else None)
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
