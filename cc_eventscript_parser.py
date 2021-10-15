import json, os, re, argparse
import CCEvents as Events
import CCUtils
from CCEvents import ChangeVarType, CommonEvent
from enum import Enum

# ~ crosscode eventscript v2.0.0-alpha parser, by EL ~
# to run:
#   python cc-eventscript-parser.py <input text file>
# REQUIRES PYTHON 3.10 OR ABOVE!
# to make a text file:
#   see readme

verbose = False

class CCES_Exception(Exception): 
    "Exceptions related to errors in an CC EventScript file."

class ParserException(Exception):
    "General exceptions related to the parser itself."

class CCEventRegex:
    # matches lines that start with "#" or "//"
    comment = re.compile(r"(?<!\\)(?:\/\/).*")


    # matches strings of the form "import (fileName)"
    importFile = re.compile(r"^import\s+(?:(?:\.\/)?patches\/)?(?P<directory>(?:[.\w]+[\\\/])*)?(?P<filename>[\w+-]+){1}?(?P<extension>\.json(?:\.patch)?)?", flags=re.I)
    includeFile = re.compile(r"^include\s+(?:(?:\.\/)?patches\/)?(?P<directory>(?:[.\w]+[\\\/])*)?(?P<filename>[\w+-]+){1}?(?P<extension>\.json(?:\.patch)?)?", flags=re.I)
    
    filepath = re.compile(r"^(?P<directory>(?:[.\w]+[\\\/])*)(?P<filename>\S+)$")
    # matches strings of the form "(character) > (expression): (message)" or "(character) > (expression) (message)"
    dialogue = re.compile(r"^(?P<character>.+)\s*>\s*(?P<expression>[A-Z\d_]+)[\s:](?P<dialogue>.+)$")
    # matches strings of the form "message (number)", insensitive search
    eventHeader = re.compile(r"^(?:message|event) (?P<eventNum>\d+):?$", flags=re.I)
    # matches strings of the form "== title =="
    title = re.compile(r"^== *(?P<ignore>!)?(?P<eventTitle>\S+) *==$")
    # matches strings of the form "(key): (value)"
    property = re.compile(r"^(?P<property>\w+)\s*:\s*(?P<value>.+)$")
    # matches "set (varname) (true/false)"
    setVarBool = re.compile(r"^set\s+(?P<varName>\S+)\s*(?P<sign>[= |^])\s*(?P<value>true|false)$", flags=re.I)
    # matches "set (varname) (+/-/=) (number)"
    setVarNum = re.compile(r"^set\s+(?P<varName>\S+)\s*(?P<operation>[=+\-*/%|^])\s*(?P<value>\d+)$", flags=re.I)

    label = re.compile(r"label +(?P<name>\S+)", flags=re.I)
    gotoLabel = re.compile(r"goto +(?P<name>\S+)(?: +if +(?P<condition>.+))?", flags=re.I)

    propertyType = re.compile(r"^type(?:\.(?P<property>\S+))?\s*:\s*(?P<value>.+)", flags = re.I)
    listOfNumbers = re.compile(r"^(?:\d+,\s*)+")
    listOfStrings = re.compile(r"^(?:\S+,\s*)+")

    # matches "if (condition)", "else", and  "endif" respectively
    ifStatement = re.compile(r"^if (?P<condition>.+)", flags=re.I)
    elseStatement = re.compile(r"^else$", flags=re.I)
    endifStatement = re.compile(r"^endif$", flags=re.I)

class EventItemType(Enum):
    STANDARD_EVENT = 1
    IMPORT = 2
    INCLUDE = 3

class ParserMode(Enum):
    NORMAL = 0
    EVENT = 1
    IF = 2
    ELSE = 3

class FileParser:
    def __init__(self, filename: str) -> None:
        with open(filename, "r") as file: 
            self.fileLines: list[str] = file.readlines()
        self.line_num: int = 1
        self.total_lines = len(self.fileLines)
        self.line_bookmark: int | None = None
        self.currentState: ParserMode = ParserMode.NORMAL

    @property
    def lines(self) -> str:
        while self.line_num <= self.total_lines: 
            newLine = CCEventRegex.comment.sub("", self.fileLines[self.line_num - 1]).strip()
            
            # skip any blank lines
            if not newLine: 
                self.line_num += 1
                continue

            yield newLine
            self.line_num += 1
        return

    def setBookmark(self):
        if(self.line_bookmark is None):
            raise ParserException("Bookmark is already set!")
        self.line_bookmark = self.line_num

    def returnToBookmark(self):
        if(self.line_bookmark is None):
            raise ParserException("Bookmark not set!")
        self.line_num = self.line_bookmark
        self.line_bookmark = None

class EventItem:
    def __init__(self, eventType, filePath: str, event: Events.CommonEvent | None = None) -> None:
        self.eventType = eventType
        if not CCEventRegex.filepath.match(filePath): raise CCES_Exception(f"Error: Invalid file path {filePath}!")
        self.filepath = filePath
        self.event = event

    def genPatchStep(self) -> dict:
        fixedFilename = re.sub(r"^(\.\/)","mod:", self.filepath)
        match self.eventType:
            case EventItemType.IMPORT | EventItemType.STANDARD_EVENT:
                return {
                    "type": "IMPORT",
                    "src": fixedFilename
                }
            case EventItemType.INCLUDE:
                return {
                    "type": "INCLUDE",
                    "src": fixedFilename
                }
            case _:
                raise CCES_Exception("Unknown patch type!")


def processDialogue(inputString: str) -> Events.SHOW_SIDE_MSG:
    messageMatch = CCEventRegex.dialogue.match(inputString)
    character = CCUtils.Character(*messageMatch.group("character", "expression"))
    message = messageMatch.group("dialogue").replace("\\n","\n")

    messageEvent = Events.SHOW_SIDE_MSG(character, message)
    return messageEvent


def processEvents(parser: FileParser) -> list[Events.Event_Step]:
    workingEvent: list[Events.Event_Step] = []
    parser.line_num += 1
    for line in parser.lines:        
        # return to previous state
        if CCEventRegex.eventHeader.match(line) or CCEventRegex.title.match(line):
            parser.line_num -= 1
            return workingEvent
        # if (condition)
        elif match := CCEventRegex.ifStatement.match(line):
            prevState: ParserMode = parser.currentState
            parser.currentState = ParserMode.IF
            ifEvent = Events.IF(match.group("condition"))
            ifEvent.thenStep = processEvents(parser)
            if parser.currentState == ParserMode.ELSE:
                ifEvent.elseStep = processEvents(parser)
            parser.currentState = prevState
            workingEvent.append(ifEvent)

        # endif
        elif CCEventRegex.endifStatement.match(line):
            # only count the last "endif" of a block
            if parser.currentState not in [ParserMode.IF, ParserMode.ELSE]:
                raise CCES_Exception("'endif' found outside of if block")
            
            return workingEvent

        # else
        elif CCEventRegex.elseStatement.match(line):
            if parser.currentState == ParserMode.ELSE:
                raise CCES_Exception("multiple 'else' statements found inside of if block")
            elif parser.currentState != ParserMode.IF:
                raise CCES_Exception("'else' statement found outside of if block")
            else:
                parser.currentState = ParserMode.ELSE
                return workingEvent

        # dialogue
        elif match := CCEventRegex.dialogue.match(line):
            workingEvent.append(processDialogue(line))

        # set var = bool
        elif match := CCEventRegex.setVarBool.match(line):
            varName, sign, originalValue = match.group("varName", "sign", "value")
            value = (originalValue.lower() == "true")
            operation: ChangeVarType
            match sign:
                case "=" | " ":
                    operation = ChangeVarType.SET
                case "|":
                    operation = ChangeVarType.OR
                case "^":
                    operation = Events.ChangeVarType.XOR 

            workingEvent.append(Events.CHANGE_VAR_BOOL(varName, value, operation))

        # set var +|-|= num
        elif match := CCEventRegex.setVarNum.match(line):
            varName, sign, number = match.group("varName", "operation", "value")
            value = int(number)
            operation: ChangeVarType
            match sign:
                case "=":
                    operation = ChangeVarType.SET
                case "+":
                    operation = ChangeVarType.ADD
                case "-":
                    operation = ChangeVarType.SUB
                case "*":
                    operation = ChangeVarType.MUL
                case "/":
                    operation = ChangeVarType.DIV
                case "%":
                    operation = ChangeVarType.MOD
                case "|":
                    operation = ChangeVarType.OR
                case "^":
                    operation = Events.ChangeVarType.XOR 
            workingEvent.append(Events.CHANGE_VAR_NUMBER(varName, value, operation))

        elif match := CCEventRegex.label.match(line):
            workingEvent.append(Events.LABEL(match.group("name")))

        elif match := CCEventRegex.gotoLabel.match(line):
            if match.group("condition"): # if a condition exists, it will do GOTO_LABEL_WHILE instead.
                workingEvent.append(Events.GOTO_LABEL_WHILE(*match.group("name", "condition")))
            else:
                workingEvent.append(Events.GOTO_LABEL(match.group("name")))

    #ensure that ifs are properly terminated
    if parser.currentState == ParserMode.IF:
        raise CCES_Exception("'if' found without corresponding 'endif'")

    return workingEvent


def handleEvent(parser: FileParser) -> Events.CommonEvent:
    event = Events.CommonEvent(type={}, loopCount = 3)

    eventNumber: int = 0
    buffer: list[str] = []
    trackMessages: bool = False
    workingEvent = {}

    parser.line_num += 1
    for line in parser.lines:
        if match := CCEventRegex.title.match(line):
            parser.line_num -= 1
            return event
        elif match := CCEventRegex.eventHeader.match(line):
            workingEvent = Events.IF(f"call.runCount == {eventNumber}")
            parser.currentState = ParserMode.EVENT
            try:
                workingEvent.thenStep = processEvents(parser)
            except CCES_Exception as e:
                raise CCES_Exception(f"error in event {eventNumber}") from e
            event.event[eventNumber] = workingEvent

            eventNumber += 1
            parser.currentState = ParserMode.NORMAL
            #trackMessages = True

        elif trackMessages:
            buffer.append(line) 

        elif match := CCEventRegex.propertyType.match(line):
            propertyName, propertyValue = match.group("property", "value")
            propertyValue = propertyValue.strip()
            if propertyName is not None:
                
                if CCEventRegex.listOfNumbers.match(propertyValue):
                    typeValueList = propertyValue.split(",")
                    event.type[propertyName] = [int(value) for value in typeValueList]

                elif CCEventRegex.listOfStrings.match(propertyValue):
                    typeValueList = propertyValue.split(",")
                    event.type[propertyName] = [value.strip() for value in typeValueList]

                elif re.match(r"^\d+$", propertyValue):
                    event.type[propertyName] = int(propertyValue)
                else:
                    event.type[propertyName] = propertyValue
                    
            else:
                event.type["type"] = propertyValue

        elif match := CCEventRegex.property.match(line):
            propertyName, propertyValue = match.group("property", "value")
            propertyName = propertyName.lower()
            
            match propertyName:
                case "frequency": event.frequency = propertyValue
                case "repeat": event.repeat = propertyValue
                case "condition": event.condition = propertyValue
                case "eventtype": event.eventType = propertyValue
                case "loopcount": event.loopCount = int(propertyValue)
                case _: raise CCES_Exception(f"unrecognized property \"{propertyName}\"")

        else:
            raise CCES_Exception(f"Unrecognized line \"{line}\", ignoring...")
    #if buffer:
    #    try:
    #        workingEvent.thenStep = processEvents(buffer)
    #    except CCES_Exception as e:
    #        raise CCES_Exception(f"error in message {eventNumber}") from e
    #    event.event[eventNumber] = workingEvent
    if event.type == {}:
        event.type = {"killCount": 0, "type": "BATTLE_OVER"}
    return event


def readFile(filename: str) -> dict[str, CommonEvent]:
    eventDict: dict[str, CommonEvent] = {}
    eventTitle: str = ""
    #buffer: list[str] = []
    beganEvents: bool = False
    ignoreEvent: bool = False
    parser = FileParser(filename)
    try:
        for line in parser.lines:
            # handle file imports
            if (match := CCEventRegex.importFile.match(line)) and (not beganEvents):
                ext = match.group('extension') or '.json'
                filename = f"./patches/{match.group('directory')}{match.group('filename')}{ext}"
                eventTitle = match.group("filename")
                if eventTitle in eventDict: raise KeyError(f"Duplicate event name '{eventTitle}' found in input file.")
                eventDict[eventTitle] = EventItem(EventItemType.IMPORT, filename)
                eventTitle = ""

            elif (not beganEvents) and (match := CCEventRegex.includeFile.match(line)):
                ext = match.group('extension') or '.json'
                filename = f"./patches/{match.group('directory')}{match.group('filename')}{ext}"
                eventTitle = match.group("filename")
                if eventTitle in eventDict: raise KeyError(f"Duplicate event name '{eventTitle}' found in input file.")
                eventDict[eventTitle] = EventItem(EventItemType.INCLUDE, filename)
                eventTitle = ""

            elif match := CCEventRegex.title.match(line):
                beganEvents = True
                # check that the event isn't empty so it only runs if there's actually something there
                #if buffer: 
                #    eventDict[eventTitle].event = handleEvent(buffer)
                #    eventTitle = ""

                # set the current event and clear the buffer
                eventTitle = match.group("eventTitle").replace("/",".")
                filename = f"./patches/{eventTitle}.json"
                #buffer = []
                
                if match.group("ignore"):
                    ignoreEvent = True
                    continue
                ignoreEvent = False
                if eventTitle in eventDict: raise KeyError("Duplicate event name found in input file.")
                eventDict[eventTitle] = EventItem(EventItemType.STANDARD_EVENT, filename, None)
                eventDict[eventTitle].event = handleEvent(parser)

            # raise error to skip event processing
            elif not ignoreEvent:
                raise CCES_Exception(f"syntax error: unexpected line '{line}'")
                #if not ignoreEvent: buffer.append(line)

            # process any final events if one is present
        #if buffer: eventDict[eventTitle].event = handleEvent(buffer)
        return eventDict
    except Exception as e:
        raise CCES_Exception(f"error on line {parser.line_num}: {e.args}") from e


def parseFiles(inputFilenames: list[str], runRecursively: bool = False) -> dict[str, EventItem]:
    eventDict: dict[str, EventItem] = {}
    filelist: list[str] = []
    if runRecursively:
        for item in os.listdir(inputFilenames[0]):
            if (not item.startswith("!")) and re.match(r".*\.cces", item):
                filelist.append(f"{inputFilenames[0]}/{item}")
    else:
        filelist = inputFilenames
    for filename in filelist:
        try: 
            eventDict |= readFile(filename)
        except CCES_Exception as e:
            raise Exception(f"Error in {filename}: ") from e
    return eventDict

def generatePatchFile(events: dict[str, EventItem]) -> list[dict]:
    patchDict: list[dict] = []
    patchDict.append({"type": "ENTER", "index": "commonEvents"})
    for event in events.values():
        patchDict.append(event.genPatchStep())
    patchDict.append({"type": "EXIT"})
    return patchDict

def writeEventFiles(events: dict[str, EventItem], indentation = None) -> None:
    os.makedirs("./patches/", exist_ok = True)
    for eventName, eventInfo in events.items():
        filename = eventInfo.filepath
        directoryMatch = CCEventRegex.filepath.match(filename)
        if directoryMatch and directoryMatch.group("directory"): os.makedirs(directoryMatch.group("directory"), exist_ok= True)
        if eventInfo.eventType == EventItemType.STANDARD_EVENT:
            if eventInfo.event is None: continue
            if verbose: print(f"Writing file '{filename}'.")
            with open(filename, "w+") as jsonFile:
                json.dump({eventName: eventInfo.event.asDict()}, jsonFile, indent = indentation)

def writeDatabasePatchfile(patchDict: dict, filename: str, indentation = None) -> None:
    filename = filename.strip()
    fileMatch = CCEventRegex.filepath.match(filename)
    os.makedirs(fileMatch.group("directory"), exist_ok = True)
    if verbose:
        print("Writing patch file at ./assets/data/database.json.patch")
    with open(filename, "w+") as patchFile:
        json.dump(patchDict, patchFile, indent = indentation)


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description= "Process a cc-eventscript file and produce the relevant .json and patch files.")
    argparser.add_argument("file", help="The eventscript file(s) to be processed. A file path if -r is enabled.", nargs = "+")
    argparser.add_argument("-i", "--indent", type = int, default = None, dest = "indentation", metavar = "NUM", nargs = "?", const = 4, help = "the indentation outputted files should use, if any. if supplied without a number, will default to 4 spaces")
    argparser.add_argument("-v", "--verbose", action="store_true", help = "increases verbosity of output")
    argparser.add_argument("-r", action = "store_true", dest = "recursive", help = "will parse all files in a single directory ending in '.cces', rather than a single file. ")
    
    databaseGroup = argparser.add_mutually_exclusive_group()
    databaseGroup.add_argument("--no-patch-file", action = "store_false", dest = "genPatch", help = "do not generate a 'database.json.patch' file")
    databaseGroup.add_argument("-p", "--patch-file", default = "./assets/data/database.json.patch", dest = "databaseFile", metavar = "DATABASE", help = "the location of the database patch file")



    args = argparser.parse_args()
    inputFiles = args.file
    verbose = args.verbose

    allEvents = parseFiles(inputFiles, args.recursive)
    writeEventFiles(allEvents, args.indentation)
    if args.genPatch: writeDatabasePatchfile(generatePatchFile(allEvents), args.databaseFile, args.indentation)
