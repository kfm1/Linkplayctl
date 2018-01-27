#!/usr/bin/env bash

#
# Reboot given devices over and over -- useful for testing the quiet and safe reboot functionality
#

# All the linkplay devices that should be rebooted:
DEVICES=("192.168.2.81" "192.168.2.82" "192.168.2.83" "192.168.2.84")

# Number of times to reboot each device
REBOOT_COUNT="20"

# The type of reboot to do:  safe or quiet.  Empty for regular reboots.
REBOOT_TYPE="quiet"

# Seconds of delay between reboot loops.  For safe or quiet, 5 seconds is good.  For regular reboots, use 60.
REBOOT_DELAY="5"


# Path to linkplayctl bash script
#   Default: ../bin/linkplayctl
#LINKPLAYCTL="../bin/linkplayctl"


printf "\n\nStarting linkplayctl device reboot loop script...\n\n"

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

i="1"
max_loops=$[${REBOOT_COUNT}+1]

while [ $i -lt ${max_loops} ]; do

    printf "Loop # ${i} of ${REBOOT_COUNT}...\n\n"

    # Reboot all
    for device in "${DEVICES[@]}"
    do
        ${LINKPLAYCTL} -v ${device} ${REBOOT_TYPE} reboot
        printf "\n"
    done

    printf "Sleeping ${REBOOT_DELAY} seconds...\n"
    sleep ${REBOOT_DELAY}

    # Reboot all
    for device in "${DEVICES[@]}"
    do
        ${LINKPLAYCTL} -v ${device} volume
        printf "\n"
    done

    printf "Sleeping 5 seconds...\n"
    sleep 5

    printf "\n"
    i=$[$i+1]
done