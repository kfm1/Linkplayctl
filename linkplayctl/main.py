import sys
import os
import argparse
import logging
import platform
import requests
import subprocess
from datetime import datetime

try:
    sys.path.index(os.path.join(sys.path[0], os.pardir))
except ValueError:
    sys.path.append(os.path.join(sys.path[0], os.pardir))

import linkplayctl

if __name__ != '__main__':
    exit()

parser = argparse.ArgumentParser(description='Control a linkplay device.', usage='%(prog)s [--help] [-v...] address command')
parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase logging verbosity (up to -vvv)")
parser.add_argument('address', type=str, help='address (hostname or ip) of device')
parser.add_argument('commands', nargs='+', metavar="command", help='one or more words to send to device')
args = parser.parse_args()

verbosity_to_log_level_map = {0: logging.ERROR, 1: logging.INFO, 2: logging.DEBUG}
log_level = verbosity_to_log_level_map[max(0, min(2, args.verbosity))]

logging.basicConfig(stream=sys.stdout, level=log_level)
log = logging.getLogger('linkplayctl').getChild('main')

try:
    git_version = subprocess.check_output(["git", "describe", "--long", "--always", "--dirty"],
                                          cwd=os.path.dirname(os.path.realpath(__file__))).strip().decode("utf-8")
except subprocess.CalledProcessError:
    git_version = "------"

full_version = linkplayctl.__version__+"  (git "+git_version+")"
log.info("======   "+datetime.now().strftime("%Y-%m-%d %H:%M")+"  Device: "+str(args.address)+"  v"+full_version+"   =====")
log.debug("Command Line: "+os.path.basename(sys.argv[0])+" "+" ".join(sys.argv[1:]))
log.debug("Linkplayctl "+full_version+"  Python "+platform.python_version()+"  Requests "+requests.__version__)
log.debug("Device address: '"+str(args.address)+"' Verbosity: "+str(args.verbosity)+
          ' Log Level: '+logging.getLevelName(log_level))

client = linkplayctl.Client(args.address, logger=logging.getLogger('linkplayctl').getChild('client'))

# Some versions of urllib3 emit too much noise at the INFO log level:
if log_level > logging.DEBUG:
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# First, find the best match for command among the API client's methods
# Start by assuming all command words are part of the method name, then uncurry as needed
cur_command_words = list(args.commands)
cur_arguments = []

if "-" in " ".join(cur_command_words):
    log.debug("Note: Hyphens in possible method names will be replaced with underscores")

while True:
    if len(cur_command_words) < 1:
        log.warn("Unable to extract a client method from "+str(args.commands)+". Aborting...")
        print("ERROR - Unknown API command '"+" ".join(args.commands)+"'.  Use --help or README for help.")
        sys.exit(2)

    command_phrase = '_'.join(cur_command_words)
    if "-" in command_phrase:
        command_phrase = command_phrase.replace("-", "_")
    log.debug("Searching for '" + command_phrase + "' method in API client attributes...")
    if hasattr(client, command_phrase):
        break
    new_argument = cur_command_words.pop()
    cur_arguments.insert(0, new_argument)

log.debug("Found client method '" + command_phrase + "'"
          + (" with argument(s) ["+' '.join(cur_arguments)+"]" if cur_arguments else ""))

# Call the located method:
log.debug("Calling '" + command_phrase + "(" + ', '.join(cur_arguments) + ")'")
try:
    attribute = getattr(client, command_phrase)
    response = attribute(*cur_arguments)
except Exception as e:
    if args.verbosity > 1:
        log.error(e, exc_info=(args.verbosity > 2))
    print("ERROR - "+str(e))
    sys.exit(1)

log.debug("Received response from API client:")
print(str(response))
sys.exit(0)
