#!/usr/bin/env bash

# Reboot and reset volume and voice prompts for a list of linkplay devices
#
# Linkplay devices get unstable after being up for too long.  This script takes a list of devices and
# performs the following actions on each one:
#   * Quiet reboot
#   * Disable voice prompts and chimes
#   * Set volume to a default value
#   * TODO: Set muting to a default value

# List of all the linkplay devices that should be reset:
DEVICES=("192.168.2.81" "192.168.2.82" "192.168.2.83" "192.168.2.84")

# Volume that each device should be set to after reboot, comment out to leave volume unchanged:
DEFAULT_VOLUME=50

printf "\n\nStarting linkplayctl device reset script...\n"

# Find linkplayctl script if not set
if [ -z "${LINKPLAYCTL}" ]
then
    this_script=$(readlink -f "$0")
    this_script_path=$(dirname "$this_script")
    LINKPLAYCTL="${this_script_path}/../bin/linkplayctl"
fi

# Make sure linkplayctl script is executable
if [ ! -x "${LINKPLAYCTL}" ]
then
    printf "ERROR: Missing or non-executable linkplayctl script: ${LINKPLAYCTL}"
    exit 1
fi

# Iterate through all devices
for device in "${DEVICES[@]}"
do
    printf "\nDevice: ${device}\n\n"

    # Print device name
    ${LINKPLAYCTL} -v ${device} name
    printf '\n'
    sleep 2

    # Print current volume setting
    ${LINKPLAYCTL} -v ${device} volume
    printf '\n'
    sleep 2

    # Reboot device quietly
    ${LINKPLAYCTL} -v ${device} quiet-reboot
    printf '\n'
    sleep 2

    # Turn off annoying voice prompts
    ${LINKPLAYCTL} -v ${device} prompt off
    printf '\n'
    sleep 2

    # Set device to new volume, if provided
    if [[ ! -z "${DEFAULT_VOLUME}" ]]
    then
        ${LINKPLAYCTL} -v ${device} volume ${DEFAULT_VOLUME}
        printf '\n'
        sleep 2

        ${LINKPLAYCTL} -v ${device} volume
        printf '\n'
        sleep 2
    fi

done
