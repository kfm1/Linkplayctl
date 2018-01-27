import logging
import time
import requests
import json
import math
import linkplayctl


class Client:
    """Simple Linkplay API client"""

    def __init__(self, address, api_version=1, logger=None):
        self._address = address
        self._api_version = api_version
        self._logger = logger if logger else logging.getLogger('linkplayctl.client')
        self._reboot_delay = 60000          # Milliseconds to wait after a reboot for device to come back up
        self._quiet_reboot_volume = 1       # Set device to this volume when doing quiet reboots
        self._intercommand_delay = 2000     # Minimum milliseconds to wait between sending commands to a device
        self._last_command_time = 0
        self.api_status_code = None
        self._equalizer_modes = {'off': 0, 'classical': 1, 'pop': 2, 'jazz': 3, 'vocal': 4}
        self._player_modes = {'none': 0, 'airplay': 1, 'dlna': 2, 'wiimu': 10, 'wiimu-local': 11, 'wiimu-station': 12,
                              'wiimu-radio': 13, 'wiimu-songlist': 14, 'wiimu-max': 19, 'http': 20, 'http-local':21,
                              'http-max': 29, 'alarm': 30, 'line-in': 40, 'bluetooth': 41, 'ext-local': 42,
                              'optical': 43, 'line-in-max': 49, 'mirror': 50, 'talk': 60, 'slave': 99}
        self._loop_modes = {'repeat:off:shuffle:off': -1, 'repeat:all:shuffle:off': 0,  'repeat:one:shuffle:off': 1,
                            'repeat:off:shuffle:on':   3, 'repeat:all:shuffle:on':  2}
        self._wifi_statuses = {'connecting': 'PROCESS', 'error-password': 'PAIRFAIL',
                               'disconnected': 'FAIL', 'connected': 'ok'}
        self._auth_types = {'off': 0, 'psk': 1}
        self._session = None

    ''' Basic Information & Commands '''

    def info(self) -> dict:
        """Retrieve combined device and player information"""
        self._logger.info("Retrieving combined device and player info...")
        device_status = self._device_info()
        player_status = self._player_info()
        status = device_status.copy()
        status.update(player_status)
        return status

    def reboot(self) -> str:
        """Request an immediate device reboot"""
        self._logger.info("Requesting reboot...")
        return self._reboot()

    def _reboot(self) -> str:
        """Internal, non-blocking method for performing reboots"""
        response = self._send("reboot")
        if response.status_code != 200 or response.content.decode("utf-8") != "OK":
            raise linkplayctl.APIException("Failed to reboot: " +
                                           "Status "+str(response.status_code)+" Content: "+response.content)
        return response.content.decode("utf-8")

    def safe_reboot(self, max_retries: int=3) -> str:
        """Request a verified reboot, retrying up to <max_tries> times if necessary"""
        self._logger.info("Requesting safe reboot...")
        if self._reboot_delay > 5000:
            sleep_length = max(0, round(self._reboot_delay / 1000.0))
            self._logger.info("Note: This call may take "+str(sleep_length)+" seconds or more to return")
        return self._safe_reboot(max_retries)

    def _safe_reboot(self, max_retries: int=3) -> str:
        t0 = time.time()
        try_count = 1
        while try_count <= max_retries+1 or max_retries < 0:
            self._logger.debug("Starting reboot attempt "+str(try_count)+" of " +
                               (str(max_retries+1) if max_retries >= 0 else "<unlimited>")+"...")
            self._logger.debug("Requesting reboot...")
            self._reboot()
            sleep_length = max(0, round(self._reboot_delay / 1000.0))
            self._logger.debug("Waiting "+str(sleep_length)+" seconds while device reboots...")
            time.sleep(sleep_length)
            self._logger.debug("Verifying device is back up and responsive after reboot...")
            if self._check():
                break
            # This reboot attempt failed.  Try again or give up:
            if try_count >= max_retries+1:
                raise linkplayctl.APIException("Failed to bring device back up after " + str(max_retries) +
                                               " reboot attempts. Giving up.")
            self._logger.debug("Device is not responding after reboot. Trying again...")
            try_count = try_count + 1
        # Reboot was successful
        elapsed_time = "{:,}".format(round((time.time()-t0), 1))
        if try_count > 1:
            self._logger.info("Safe reboot required " + str(try_count) + " attempts and "+elapsed_time+" seconds.")
        else:
            self._logger.debug("Safe reboot complete first attempt and " + elapsed_time + " seconds.")
        return "OK"

    def reboot_safe(self, max_retries: int=3) -> str:
        """Alias for safe_reboot()"""
        return self.safe_reboot(max_retries)

    def _check(self) -> bool:
        """Return True if device is reachable and responsive, false otherwise"""
        # Check if player_info() request returns an error (an APIException or invalid data)
        try:
            info = self._player_info()
        except (linkplayctl.APIException, linkplayctl.ConnectionException) as e:
            self._logger.debug("Device is not okay: "+str(e))
            return False
        if not isinstance(info, dict) or 'vol' not in info.keys():
            self._logger.debug("Device is not okay: Missing info dictionary or volume key")
            return False
        return True

    def quiet_reboot(self) -> str:
        """Reboot the device quietly, i.e., without boot jingle. Returns when complete, usually ~120 seconds."""
        t0 = time.time()
        sleep_length = max(0, round(self._reboot_delay/1000.0))
        self._logger.info("Requesting quiet reboot...")
        if self._reboot_delay > 5000:
            self._logger.info("Note: This call may take "+str(sleep_length)+" seconds or more to return")
        self._logger.debug("Getting current volume...")
        old_volume = self._volume()
        self._logger.debug("Saving current volume '"+str(old_volume)+"' and setting new volume to '" +
                           str(self._quiet_reboot_volume)+"'...")
        self._volume(self._quiet_reboot_volume)
        self._logger.debug("Verifying volume has been correctly set to minimum...")
        if int(self._volume()) != self._quiet_reboot_volume:
            raise linkplayctl.APIException("Failed to set volume to minimum before quiet reboot")
        self._safe_reboot()
        self._logger.debug("Restoring previous volume '" + str(old_volume) + "'...")
        self._volume(old_volume)
        self._logger.debug("Confirming new volume is set to '" + str(old_volume) + "'...")
        if old_volume != int(self._volume()):
            raise linkplayctl.APIException("Failed to restore old volume '"+str(old_volume)+"' after reboot")
        elapsed_time = "{:,}".format(round((time.time()-t0)*1000, 1))
        self._logger.debug("Quiet reboot complete.  Elapsed time: "+str(elapsed_time)+"ms")
        return "OK"

    def reboot_quiet(self) -> str:
        """Alias for quiet_reboot()"""
        return self.quiet_reboot()

    def silent_reboot(self) -> str:
        """Alias for quiet_reboot()"""
        return self.quiet_reboot()

    def reboot_silent(self) -> str:
        """Alias for quiet_reboot()"""
        return self.quiet_reboot()

    def shutdown(self) -> str:
        """Request an immediate device shutdown"""
        self._logger.info("Requesting shutdown...")
        response = self._send("getShutdown")
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to shutdown: Status code="+str(response.status_code))
        return response.content.decode("utf-8")

    def command(self, text) -> object:
        """Send given text as a command to device and return result"""
        self._logger.info("Executing command '"+str(text)+"'...")
        response = self._send(text)
        return response.content

    ''' Device Information & Settings '''

    def device_info(self) -> dict:
        """Retrieve device and hardware info, such as name, firmware, etc."""
        self._logger.info("Retrieving device info...")
        return self._device_info()

    def _device_info(self) -> dict:
        """Internal method to retrieve device status"""
        response = self._send("getStatus")
        return self._json_decode(response)

    def name(self, name: str = None) -> str:
        """Get or set the device name to be used for services such as Airplay"""
        if not name:
            self._logger.info("Retrieving device name...")
            return self._device_info().get("DeviceName")
        self._logger.info("Setting device name to '"+str(name)+"'...")
        if not isinstance(name, str) or not name:
            raise AttributeError("Device name must be a non-empty string")
        response = self._send("setDeviceName:"+name)
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to set device name to '"+name+"'")
        return response.content.decode("utf-8")

    def group(self) -> str:
        """Get the name of the multiroom group to which the device belongs"""  # TODO: Same as multiroom master?
        self._logger.info("Retrieving device group name...")
        return self._device_info().get("GroupName")

    def uuid(self) -> str:
        """Get the device's UUID"""
        self._logger.info("Retrieving device UUID...")
        return self._device_info().get("uuid")

    def hardware(self) -> str:
        """Get the device's hardware version"""
        self._logger.info("Retrieving device hardware version...")
        return self._device_info().get("hardware")

    def model(self) -> str:
        """Get the device's model name (aka project name)"""
        self._logger.info("Retrieving device model name (aka project)...")
        return self._device_info().get("project")

    ''' WiFi Status & Connections '''

    def wifi_ssid(self) -> str:
        """Get the device's WiFi access point SSID"""
        self._logger.info("Retrieving WiFi SSID...")
        return self._device_info().get("ssid")

    def wifi_ssid_hidden(self) -> bool:
        """Returns True if the device's WiFi's SSID is hidden, False otherwise"""
        self._logger.info("Retrieving WiFi hidden SSID flag...")
        return int(self._device_info().get("hideSSID")) == 1

    def wifi_channel(self) -> int:
        """Returns the current channel of the device's WiFi radio"""
        self._logger.info("Retrieving WiFi channel...")
        return int(self._device_info().get("WifiChannel"))

    def wifi_power(self, power: object = None) -> object:
        """Get or set the current power of the wifi radio--currently, only supports setting to OFF/0"""
        if power is None:
            self._logger.info("Retrieving current WiFi radio power... [NOT IMPLEMENTED]")
            raise NotImplementedError("Command 'wifi_power' is not implemented yet")
        if (isinstance(power, str) and power.lower() == 'off') or not power:
            return self.wifi_off()
        raise NotImplementedError("Command 'wifi_power(<value>)' is not implemented yet")

    def wifi_mac(self) -> str:
        """Get the MAC of the wifi radio"""
        self._logger.info("Retrieving WiFi MAC address...")
        return self._device_info().get("MAC")

    def wifi_auth(self, auth_type: str = None, new_pass: str = None):
        """Get or set the network authentication parameters

            :returns: str Device response (usually "OK") if set, dict of auth values if get
        """
        if auth_type is None:
            self._logger.info("Retrieving WiFi authentication information...")
            return {k: v for (k, v) in self._device_info().items() if (k in ["securemode", "auth", "encry", "psk"])}
        self._logger.info("Setting WiFi authentication type to '"+str(auth_type)+"'"
                          +(" with pass '"+str(new_pass)+"'" if new_pass else "")+"...")
        try:
            auth_value = self._auth_types[auth_type]
        except KeyError:
            raise linkplayctl.APIException("Authentication type must be one of ["+", ".join(self._auth_types.keys())+"]")
        if auth_value and not new_pass:
            raise linkplayctl.APIException("Authentication type '"+str(auth_type)+"' requires a non-empty password")
        response = self._send("setNetwork:"+str(auth_value)+":"+str(new_pass) if new_pass is not None else "")
        self._logger.debug("Authentication set.  Device is rebooting...")
        return response.content.decode("utf-8")

    def wifi_networks(self) -> dict:
        """Get available WiFi access points"""
        self._logger.info("Retrieving WiFi available networks list...")
        return self._json_decode(self._send("wlanGetApList"))

    def wifi_status(self) -> str:
        """Get the current status of the WiFi connection"""
        self._logger.info("Retrieving WiFi connection status...")
        inverse_wifi_statuses = {v: k for k, v in self._wifi_statuses.items()}
        response = self._send("wlanGetConnectState").content.decode("utf-8")
        try:
            return inverse_wifi_statuses[response]
        except KeyError:
            raise linkplayctl.APIException("Received unrecognized wifi status: '"+str(response)+"'")

    def wifi_off(self) -> str:
        """Disable the WiFi radio"""
        self._logger.info("Turning off WiFi radio...")
        return self._send("setWifiPowerDown").content.decode("utf-8")

    ''' Player Status & Commands '''

    def player_info(self) -> dict:
        """Get player subsystem information, such as current title, volume, etc."""
        self._logger.info("Retrieving player information...")
        return self._player_info()

    def _player_info(self) -> dict:
        """Internal method to retrieve player subsystem information."""
        return self._json_decode(self._send("getPlayerStatus"))

    def transport(self) -> str:
        """Get current transport status, e.g., play, pause, etc...."""
        self._logger.info("Retrieving current transport status, e.g., play, pause, stop.")
        self._logger.info("Note: Devices report incorrect transport status for some streams, such as airplay/dlna")
        return self._player_info().get('status')

    def play(self, uri: str = None) -> str:
        """Start playback of track/playlist at uri, or current media if None"""
        self._logger.info("Starting playback of "+(("'"+str(uri)+"'") if uri else "current media")+"...")
        return self._send("setPlayerCmd:play"+(":"+str(uri) if uri else "")).content.decode("utf-8")

    def pause(self) -> str:
        """Pause playback of current media"""
        self._logger.info("Pausing playback...")
        return self._send("setPlayerCmd:pause").content.decode("utf-8")

    def resume(self) -> str:
        """Resume playback of current media"""
        self._logger.info("Resuming playback...")
        return self._send("setPlayerCmd:resume").content.decode("utf-8")

    def stop(self) -> str:
        """Stop playback of current media"""
        self._logger.info("Stop playback...")
        return self._send("setPlayerCmd:stop").content.decode("utf-8")

    def previous(self) -> str:
        """Skip backward to previous track"""
        self._logger.info("Skipping backward to previous media track...")
        return self._send("setPlayerCmd:prev").content.decode("utf-8")

    def next(self) -> str:
        """Skip forward to next track"""
        self._logger.info("Skipping forward to next media track...")
        return self._send("setPlayerCmd:next").content.decode("utf-8")

    def seek(self, val: float) -> str:
        """Move to provided time in seconds in media"""
        self._logger.info("Seeking to '" + str(val) + "' second mark in media...")
        return self._position(int(math.floor(float(val)*1000)))

    def back(self, val: float = 10) -> str:
        """Rewind playback by given seconds, default 10"""
        self._logger.info("Rewinding playback by '" + str(val) + "' seconds...")
        return self._position(int(self._position() - int(math.floor(float(val)*1000))))

    def forward(self, val: float = 10) -> str:
        """Fast-forward playback by given seconds, default 10"""
        self._logger.info("Fast-forwarding playback by '" + str(val) + "' seconds...")
        return self._position(int(self._position() + int(math.floor(float(val)*1000))))

    def _seek(self, val: float) -> str:
        """Internal method to move to provided second mark in media"""
        totlen_ms = int(self._length())
        newpos_ms = int(math.floor(float(val)*1000))
        newpos_ms = max(0, min(totlen_ms, newpos_ms))
        newpos = math.floor(newpos_ms/1000)
        self._logger.debug("Seeking to " + str(newpos) + " second mark in media "+
                           "(position "+str(newpos_ms)+" of "+str(totlen_ms)+")...")
        return self._send("setPlayerCmd:seek:"+str(newpos)).content.decode("utf-8")

    ''' Shuffle and Repeat '''

    def _loop(self, mode: str = None) -> str:
        """Internal method to get or set the current looping mode (includes shuffle and repeat setting)"""
        if mode is None:
            inverse_loop_modes = {v: k for k, v in self._loop_modes.items()}
            self._logger.debug("Requesting current loop mode...")
            loopval = self._player_info().get('loop')
            self._logger.debug("Current loop mode value is '"+str(loopval)+"'. Mapping to mode names...")
            try:
                return inverse_loop_modes[int(loopval)]
            except KeyError:
                raise linkplayctl.APIException("Received unknown loop mode value '"+str(loopval)+"' from device")
        try:
            value = self._loop_modes[str(mode)]
            self._logger.debug("Setting loop mode to '"+str(mode)+"' [value: '"+str(value)+"']...")
        except KeyError:
            try:
                value = int(mode) if int(mode) in self._loop_modes.values() else -1
            except:
                raise linkplayctl.APIException("Cannot set unknown loop mode '"+str(mode)+"'")
            inverse_loop_modes = {v: k for k, v in self._loop_modes.items()}
            self._logger.debug("Setting loop mode to '"+str(inverse_loop_modes[value])+"' [value: '" +str(value)+"']...")
        return self._send('setPlayerCmd:loopmode:'+str(value)).content.decode("utf-8")

    def shuffle(self, value: str = None) -> str:
        """Get or set the shuffle--either on/1/True to turn shuffle on, otherwise turn shuffle off"""
        if value is None:
            self._logger.info("Retrieving shuffle setting...")
            return self._loop().split(':')[3]
        self._logger.info("Setting shuffle to '"+str(value)+"'")
        shuffle = "off" if (isinstance(value, str) and (value == "off" or value == "0")) or not value else "on"
        repeat = self._loop().split(':')[1]
        return self._loop("repeat:"+repeat+":shuffle:"+shuffle)

    def repeat(self, value: str = None) -> str:
        """Get or set the repeat--'one' or 'all' or 'off'"""
        if value is None:
            self._logger.info("Retrieving repeat setting...")
            return self._loop().split(':')[1]
        self._logger.info("Setting repeat to '"+str(value)+"'")
        if isinstance(value, str) and value == "one":
            repeat = "one"
        else:
            repeat = "off" if (isinstance(value, str) and (value == "off" or value == "0")) or not value else "all"
        shuffle = "off" if repeat == "one" else self._loop().split(':')[3]
        return self._loop("repeat:"+repeat+":shuffle:"+shuffle)

    ''' Media Info '''

    def title(self) -> str:
        self._logger.info("Retrieving current media title...")
        return self._dehex(self._player_info().get('Title'))

    def album(self) -> str:
        self._logger.info("Retrieving current media album...")
        return self._dehex(self._player_info().get('Album'))

    def artist(self) -> str:
        self._logger.info("Retrieving current media artist...")
        return self._dehex(self._player_info().get('Artist'))

    def position(self, newpos_ms: int = None) -> str:
        if newpos_ms is None:
            self._logger.info("Retrieving player's current position in media...")
        else:
            self._logger.info("Setting player's position in media to "+str(newpos_ms)+"...")
        return self._position(newpos_ms)

    def _position(self, newpos_ms: int = None) -> str:
        if newpos_ms is None:
            return int(self._player_info().get('curpos'))
        self._logger.debug("Checking total media length to ensure new position is not past the end of the media...")
        totlen_ms = int(self._length())
        newpos_ms = max(0, min(totlen_ms, int(newpos_ms)))
        newpos = math.floor(newpos_ms / 1000)
        self._logger.debug("Setting player media position to "+str(newpos_ms)+" (of "+str(totlen_ms)+" ms)...")
        return self._send("setPlayerCmd:seek:"+str(newpos)).content.decode("utf-8")

    def length(self) -> int:
        self._logger.info("Retrieving total length of current media in ms...")
        return self._length()

    def _length(self) -> int:
        return int(self._player_info().get('totlen'))

    ''' Volume Control '''

    def volume(self, value: object = None):
        """ Get or set the volume to an absolute value between 0 and 100 or a relative value -100 to +100

            :returns: int volume, or "OK" on volume set
        """
        if value is None:
            self._logger.info("Retrieving device volume...")
            return self._volume()
        self._logger.info("Setting volume '"+str(value)+"'...")
        return self._volume(value)

    def _volume(self, value: object = None):
        """ Internal method to get/set volume to an absolute value between 0 and 100 or a relative value -100 to +100

            :returns: int volume, or "OK" on volume set
        """
        if value is None:
            return int(self._player_info().get("vol"))
        try:
            if isinstance(value, str) and (value.startswith('+') or value.startswith('-')):
                self._logger.debug("Adjusting volume by " + str(value) + ". Getting old volume...")
                new_volume = max(0, min(100, self._volume()+int(math.floor(float(value)))))
                self._logger.debug("Adjusting volume "+str(value)+" to "+str(new_volume)+"...")
            else:
                new_volume = max(0, min(100, int(math.floor(float(value)))))
                self._logger.debug("Setting volume to " + str(int(new_volume)))
        except ValueError:
            raise AttributeError("Volume must be between 0 and 100 or -100 to +100, inclusive, not '"+str(value)+"'")
        response = self._send("setPlayerCmd:vol:" + str(new_volume))
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to set volume to '"+str(new_volume)+"'")
        return response.content.decode("utf-8")

    def volume_up(self, value=5) -> str:
        """ Increase volume by given integer amount, defaults to plus 5

            :param value: int, float, str - Numeric
        """
        return self.volume("+"+str(value))

    def volume_down(self, value=5):
        """Decrease volume by given integer amount, defaults to minus 5"""
        return self.volume("-"+str(value))

    def mute(self, value=None):
        """Get or set the muting state. 'off' or falsy values turn muting off, otherwise muting is turned on."""
        if value is None:
            self._logger.info("Retrieving state of muting function...")
            return int(self._player_info().get("mute")) == 1
        if not value or (isinstance(value, str) and (value == '0' or value == 'off')):
            return self.mute_off()
        return self.mute_on()

    def mute_on(self) -> str:
        """Mute the device"""
        self._logger.info("Turning muting on")
        return self._send("setPlayerCmd:mute:1").content.decode("utf-8")

    def mute_off(self) -> str:
        """Unmute the device"""
        self._logger.info("Turning muting off")
        return self._send("setPlayerCmd:mute:0").content.decode("utf-8")

    ''' Source Control '''

    def source(self, mode: str = None) -> str:
        """Get the current player source, such as airplay, dlna, wiimu (playlist), bluetooth"""
        if mode is None:
            self._logger.info("Retrieving current player source (e.g., airplay, dlna, etc.)...")
            inverse_player_modes = {v: k for k, v in self._player_modes.items()}
            mode = int(self._player_info().get('mode'))
            return inverse_player_modes.get(mode)
        self._logger.info("Setting player source to '"+str(mode)+"'... [NOT IMPLEMENTED]")
        raise NotImplementedError("Method source(mode) is not implemented. Try bluetooth(), aux(), etc.")

    def playlist(self, uri: str) -> str:
        """Set player source to the playlist at the provided uri [PROBABLY NOT WORKING ON SOME DEVICES]"""
        self._logger.info("Setting player playlist to '"+str(uri)+"'...")
        self._logger.info("Note:  This call apparently does not work on some devices.  Try play(uri) instead.")
        return self._send("setPlayerCmd:playlist:"+uri).content.decode("utf-8")  # Previously: ":1" on end.

    def bluetooth(self) -> str:
        """Set player source to bluetooth"""
        self._logger.info("Setting player source to bluetooth...")
        return self._send("setPlayerCmd:switchmode:bluetooth").content.decode("utf-8")

    def aux(self) -> str:
        """Set player source to AUX/line-in)"""
        self._logger.info("Setting player source to AUX/line-in...")
        return self._send("setPlayerCmd:switchmode:line-in").content.decode("utf-8")

    def linein(self) -> str:
        return self.aux()

    def local(self, index: int=1) -> str:
        """Set player source to the local filesystem (SD, USB, etc.) and start playing at provided file index"""
        self._logger.info("Setting player source to local device (SD, USB, etc.), track number '"+str(index)+"'...")
        return self._send("setPlayerCmd:playLocalList:"+str(int(index))).content.decode("utf-8")

    def preset(self, number: int, uri: str=None) -> str:
        """If optional uri is provided, the numbered preset will be set to that uri. If no uri, then load preset by #"""
        if uri is None:
            self._logger.info("Setting device to Preset number '"+str(number)+"'...")
            return self._send("MCUKeyShortClick:"+str(self._validate_preset(number))).content.decode("utf-8")
        raise NotImplementedError("Setting preset URIs is not implemented yet (API call not known)")

    def _validate_preset(self, number: object) -> int:
        """Internal method to validate and return preset as an integer between 1 and 6, inclusive"""
        try:
            number = int(number)
            if number < 1 or number > 6:
                raise linkplayctl.APIException
        except (ValueError, linkplayctl.APIException):
            raise linkplayctl.APIException("Preset number must be an integer between 1 and 6, inclusive")
        return number

    ''' Equalizer Control '''

    def equalizer(self, mode: str=None) -> str:
        """Get or set the equalizer mode"""
        if mode is None:
            self._logger.info("Retrieving current equalizer setting...")
            inverse_eq_modes = {v: k for k, v in self._equalizer_modes.items()}
            value = self._json_decode(self._send("getEqualizer"))
            try:
                mode = inverse_eq_modes[value]
            except KeyError:
                raise linkplayctl.APIException("Received unknown equalizer mode value '"+str(value)+"'")
            self._logger.info("Received equalizer mode '"+mode+"' (value "+str(value)+")")
            return mode
        self._logger.info("Setting equalizer to '"+str(mode)+"'...")
        try:
            mode_value = self._equalizer_modes[mode]
        except KeyError:
            eq_values = ' '.join(self._equalizer_modes)
            raise AttributeError("Equalizer mode must be one of ["+eq_values+"], not '"+str(mode)+"'")
        self._logger.info("Equalizer mode '" + str(mode)+"' maps to value "+str(mode_value))
        response = self._send("setPlayerCmd:equalizer:"+str(mode_value))
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to set equalizer to mode '"+str(mode)+"' (value '"+str(mode_value)+"'")
        return response.content.decode("utf-8")

    def equalizer_modes(self) -> dict:
        """Returns the allowed equalizer modes along with their mapped values"""
        return self._equalizer_modes

    ''' Voice Prompts & Jingles '''

    def prompt(self) -> str:
        """Retrieve the voice prompt boolean--not implemented because API command is not known"""
        self._logger.info("Retrieving voice prompts setting...")
        raise NotImplementedError("Prompt() is not implemented yet.")

    def prompt_on(self) -> str:
        """Enable voice prompts and notifications"""
        self._logger.info("Turning voice prompts on...")
        response = self._send("PromptEnable")
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to enable prompts: Status code="+str(response.status_code))
        return response.content.decode("utf-8")

    def prompt_off(self) -> str:
        """Disable voice prompts and notifications"""
        self._logger.info("Turning voice prompts off...")
        response = self._send("PromptDisable")
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to disable prompts: Status code="+str(response.status_code))
        return response.content.decode("utf-8")

    def prompt_language(self, value: str=None) -> str:
        if value is None:
            self._logger.info("Getting voice prompts language...")
            return self._device_info().get('language')
        """Get or set the prompt language [SETTER NOT IMPLEMENTED]"""
        self._logger.info("Setting voice prompts language... [NOT IMPLEMENTED]")
        raise NotImplementedError("Command 'prompt_language' is not implemented yet")

    ''' Firmware Updating '''

    def firmware_version(self) -> str:
        """Get the current firmware version"""
        self._logger.info("Retrieving current firmware version")
        return self._device_info().get("firmware")

    def firmware_update_search(self) -> str:
        """Initiate a non-blocking search for new firmware"""
        self._logger.info("Starting firmware update search...")
        return self._send("getMvRemoteUpdateStartCheck").content.decode("utf-8")

    def firmware_update_available(self) -> str:
        """Display information about possible firmware updates (must call firmware_update_search() first)"""
        self._logger.info("Retrieving firmware update availability...")
        return self._json_decode(self._send("getMvRemoteUpdateStatus"))

    def firmware_update_version(self) -> str:
        """Display version of firmware update, if any (must call firmware_update_search() first)"""
        self._logger.info("Retrieving firmware update version...")
        return self._device_info().get("NewVer")

    ''' Multi-Room Setup '''

    def multiroom_info(self) -> dict:
        """Get information about the multiroom group status of this device"""
        self._logger.info("Retrieving multiroom master and slaves of this device, if any...")
        self._logger.debug("Retrieving master information...")
        try:
            master_info = {'status': 'slave', 'master': {'ip': self._device_info()['master_ip']}}
        except KeyError:
            master_info = {'status': 'master'}
        self._logger.debug("Retrieving slave information...")
        response = self._send("multiroom:getSlaveList")
        slave_info = self._json_decode(response)
        master_info.update(slave_info)
        return master_info

    def multiroom_add(self, slave_ip: str) -> str:
        """Make device at slave_ip a slave of the current device"""
        self._logger.info("Slaving '"+str(slave_ip)+"' to this device...")
        info = self._device_info()
        secure = info.get('securemode')
        args = [info.get('ssid'), info.get('WifiChannel'), info.get('auth') if secure else "OPEN",
                info.get('encry') if secure else "", info.get('psk') if secure else ""]
        self._logger.debug("Opening client connection to slave device '"+str(slave_ip)+"'...")
        slave = linkplayctl.Client(slave_ip)
        return slave.multiroom_master(*args)

    def multiroom_master(self, ssid: str, channel: int, auth: str, encryption: str, psk: str) -> str:
        """Set the multiroom master of this device"""
        self._logger.info("Requesting multiroom sync as slave to master at ssid '"+str(ssid)+"'...")
        return self._send("ConnectMasterAp:ssid=" + str(self._hex(ssid)) + ":ch=" + str(channel) + ":auth=" + auth +
                          ":encry=" + encryption + ":pwd=" + self._hex(psk) + ":chext=0").content.decode("utf-8")

    def multiroom_remove(self, slave_ip: str) -> str:
        """Remove device at slave_ip from this multiroom group"""
        self._logger.info("Removing slave '"+str(slave_ip)+"' from multiroom group")
        return self._send("multiroom:SlaveKickout:"+str(slave_ip)).content.decode("utf-8")

    def multiroom_hide(self, slave_ip: str) -> str:
        """Force given slave_ip to hide itself from the local network"""
        self._logger.info("Hiding multiroom slave '" + str(slave_ip) + "' from network list")
        return self._send("multiroom:SlaveMask:" + str(slave_ip)).content.decode("utf-8")

    def multiroom_show(self, slave_ip: str) -> str:
        """Force given slave_ip to show itself on the local network"""
        self._logger.info("Unhiding multiroom slave '" + str(slave_ip) + "' from network list")
        return self._send("multiroom:SlaveUnMask:" + str(slave_ip)).content.decode("utf-8")

    def multiroom_off(self) -> str:
        """Remove self from multiroom group and, if master, tear down the whole group"""
        self._logger.info("Tearing down the current multiroom group...")
        return self._send("multiroom:Ungroup").content.decode("utf-8")

    ''' Internal Methods '''

    def _url(self, command: str) -> str:
        """Internal method to construct url fragments from provided command"""
        return "http://" + self._address + "/httpapi.asp?command=" + command

    def _send(self, command: str) -> requests.Response:
        """Internal method to send raw fragments to the device"""
        fragment = self._url(command)
        t0 = time.time()    # time() does not necessarily have subsecond precision, but we don't absolutely require it
        delay_ms = round(self._intercommand_delay - 1000.0*(t0 - self._last_command_time))
        if delay_ms > 0:
            self._logger.debug("Waiting "+str(delay_ms)+"ms before starting another request...")
            time.sleep(delay_ms / 1000.0)
        self._logger.debug("Requesting '" + fragment + "'...")
        t0 = time.time()
        try:
            self._session = self._session if self._session else requests.session()
            response = self._session.get(fragment, timeout=30)
            self.api_status_code = response.status_code
            elapsed = round((time.time()-t0)*1000, 1)
            self._logger.debug("Response received in "+str(elapsed)+"ms " +
                               "[Status: "+str(self.api_status_code)+" Length: "+str(len(response.content))+"bytes]" +
                               ((": "+str(response.content)) if len(response.content) < 16 else ""))
            return response
        except requests.exceptions.RequestException as e:
            raise linkplayctl.ConnectionException("Could not connect to '" + str(self._address) + "': " + str(e))
        except KeyboardInterrupt:
            raise linkplayctl.ConnectionException("Connection interrupted")
        finally:
            self._last_command_time = time.time()

    def _dehex(self, hex_string: str) -> str:
        """Decode hex_string into string, if possible, otherwise return hex_string unmodified"""
        try:
            return bytearray.fromhex(hex_string).decode()
        except ValueError:
            return hex_string

    def _hex(self, string: str) -> str:
        """Encode string into hex, if possible, otherwise return string unmodified"""
        try:
            return "".join("{:02x}".format(c) for c in string.encode())
        except ValueError:
            return string

    def _json_decode(self, s: object) -> object:
        """Decode the given object as JSON"""
        try:
            s = s.content
        except AttributeError: pass
        try:
            s = s.decode("utf-8")
        except UnicodeDecodeError: pass
        try:
            return json.JSONDecoder().decode(str(s))
        except ValueError:  # json.JSONDecodeError is better for > 3.4
            raise linkplayctl.APIException("Expected JSON from API, got: '"+str(s)+"'")
