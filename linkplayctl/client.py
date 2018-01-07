import logging
import time
import requests
import math
import linkplayctl


class Client:
    """Simple Linkplay API client"""

    def __init__(self, address, api_version=1, logger=None):
        self._address = address
        self._api_version = api_version
        self._logger = logger if logger else logging.getLogger('linkplayctl.client')
        self.api_status_code = None
        self._equalizer_modes = {'off': 0, 'classical': 1, 'pop': 2, 'jazz': 3, 'vocal': 4}
        self._player_modes = {'none': 0, 'airplay': 1, 'dlna': 2, 'wiimu': 10, 'wiimu-local': 11, 'wiimu-station': 12,
                              'wiimu-radio': 13, 'wiimu-songlist': 14, 'wiimu-max': 19, 'http': 20, 'http-local':21,
                              'http-max': 29, 'alarm': 30, 'line-in': 40, 'bluetooth': 41, 'ext-local': 42,
                              'optical': 43, 'line-in-max': 49, 'mirror': 50, 'talk': 60, 'slave': 99}
        self._loop_modes = {'repeat:off:shuffle:off': -1, 'repeat:all:shuffle:off': 0,  'repeat:one:shuffle:off': 1,
                            'repeat:off:shuffle:on':   3, 'repeat:all:shuffle:on':  2}
        self._auth_types = {'off': 0, 'psk': 1}
        self._session = None

    ''' Basic Information & Commands '''

    def info(self):
        """Retrieve a combined list of unprocessed device and player information. See device_info() and player_info()"""
        self._logger.info("Retrieving combined device and player info...")
        device_status = self._device_info()
        player_status = self._player_info()
        status = device_status.copy()
        status.update(player_status)
        return status

    def reboot(self):
        """Reboot the device immediately"""
        self._logger.info("Requesting reboot...")
        return self._reboot()

    def _reboot(self):
        """Internal method for performing reboots"""
        response = self._send("reboot")
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to reboot: Status code="+str(response.status_code))
        return response.content.decode("utf-8")

    def reboot_silent(self):
        """Reboot the device quietly, i.e., without boot jingle"""
        t0 = time.time()
        self._logger.info("Requesting quiet reboot...")
        old_volume = self._volume()
        self._logger.debug("Saving current volume '"+str(old_volume)+"' and setting volume to 1...")
        self._volume(1)
        self._logger.debug("Verifying volume is correctly set to 1...")
        if 1 != int(self._volume()):
            raise linkplayctl.APIException("Failed to set volume before quiet reboot")
        self._logger.debug("Starting reboot...")
        self._reboot()
        sleep_length = 60  # 60 seconds is minimum--anything less causes device to hang on subsequent calls (e.g. info)
        self._logger.debug("Sleeping "+str(sleep_length)+" seconds while device reboots...")
        time.sleep(sleep_length)
        self._logger.debug("Restoring previous volume '" + str(old_volume) + "'")
        self._volume(old_volume)
        elapsed_time = "{:,}".format(round((time.time()-t0)*1000, 1))
        self._logger.debug("Quiet reboot complete.  Elapsed time: "+str(elapsed_time)+"ms")
        return "OK"

    def silent_reboot(self):
        """Alias for reboot_silent()"""
        return self.reboot_silent()

    def shutdown(self):
        """Shutdown the device immediately"""
        self._logger.info("Requesting shutdown...")
        response = self._send("getShutdown")
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to shutdown: Status code="+str(response.status_code))
        return response.content.decode("utf-8")

    def command(self, text):
        """Send given text as a command to device and return result"""
        self._logger.info("Executing command '"+str(text)+"'...")
        response = self._send(text)
        return response.content

    ''' Device Information & Settings '''

    def device_info(self):
        """Retrieve a list of device and hardware info, such as name, firmware, etc."""
        self._logger.info("Retrieving device info...")
        return self._device_info()

    def _device_info(self):
        """Internal method to retrieve device status"""
        response = self._send("getStatus")
        return response.json()

    def name(self, name=None):
        """Get or set the device name to be used for services such as Airplay"""
        if not name:
            self._logger.info("Retrieving device name...")
            return self._device_info().get("DeviceName")
        self._logger.info("Setting device name to '"+str(name)+"'...")
        if not isinstance(name, str) or not name:
            raise AttributeError("Device name must be a non-empty string")
        response = self._send("setDeviceName:"+name) # TODO: ToHex??
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to set device name to '"+name+"'")
        return response.content.decode("utf-8")

    def group(self):
        """Get the name of the player group to which the device belongs"""
        self._logger.info("Retrieving device group name...")
        return self._device_info().get("GroupName")

    def uuid(self):
        """Get the device's UUID"""
        self._logger.info("Retrieving device UUID...")
        return self._device_info().get("uuid")

    def hardware(self):
        """Get the device's hardware version"""
        self._logger.info("Retrieving device hardware version...")
        return self._device_info().get("hardware")

    def model(self):
        """Get the device's model name (aka project name)"""
        self._logger.info("Retrieving device model name (aka project)...")
        return self._device_info().get("project")

    ''' WiFi Status & Connections '''

    def wifi_ssid(self):
        """Get the device's WiFi access point SSID"""
        self._logger.info("Retrieving WiFi SSID...")
        return self._device_info().get("ssid")

    def wifi_ssid_hidden(self):
        """Returns True if the device's WiFi's SSID is hidden, False otherwise"""
        self._logger.info("Retrieving WiFi hidden SSID flag...")
        return int(self._device_info().get("hideSSID")) == 1

    def wifi_channel(self):
        """Returns the current channel of the device's WiFi radio"""
        self._logger.info("Retrieving WiFi channel...")
        return int(self._device_info().get("WifiChannel"))

    def wifi_power(self):
        """Get the current power of the wifi radio"""
        self._logger.info("Retrieving current WiFi radio power... [NOT IMPLEMENTED]")
        raise NotImplementedError("Command 'wifi_power' is not implemented yet")

    def wifi_mac(self):
        """Get the MAC of the wifi radio"""
        self._logger.info("Retrieving WiFi MAC address...")
        return self._device_info().get("MAC")

    def wifi_auth(self, auth_type=None, new_pass=None):
        """Get or set the network authentication parameters"""
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
        response = self._send("setNetwork:"+str(auth_value)+":"+(str(new_pass) if new_pass is not None else "")) # TODO: Pass to hex
        self._logger.debug("Authentication set.  Device is rebooting...")
        return response.content.decode("utf-8")

    def wifi_networks(self):
        """Get a list of available WiFi access points"""
        self._logger.info("Retrieving WiFi available networks list...")
        response = self._send("wlanGetApList")
        return response.json()

    def wifi_status(self):
        """Get the current status of the WiFi connection"""
        raise NotImplementedError("Command 'wifi_status' is not implemented yet")
        self._logger.info("Retrieving WiFi connection status...")
        response = self._send("wlanGetConnectState")
        return str(response.content)

    def wifi_off(self):
        """Disable the WiFi radio"""
        response = self._send("setWifiPowerDown")
        self._logger.info("Turning off WiFi radio...")
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to disable wifi: Status code="+str(response.status_code))
        return response.content.decode("utf-8")

    ''' Player Status '''

    def player_info(self):
        """Get the status of the player subsystem, such as current title, volume, etc."""
        self._logger.info("Retrieving player information...")
        return self._player_info()

    def _player_info(self):
        """Internal method to retrieve player subsystem information."""
        response = self._send("getPlayerStatus")
        return response.json()

    def player_mode(self, mode=None):
        """Get or set the current payer mode, such as airplay or dlna"""
        if mode is None:
            self._logger.info("Retrieving player mode (e.g., airplay, dlna, etc.)...")
            inverse_player_modes = {v: k for k, v in self._player_modes.items()}
            mode = int(self._player_info().get('mode'))
            return inverse_player_modes.get(mode)
        self._logger.info("Setting player mode to '"+str(mode)+"'... [NOT IMPLEMENTED]")
        self._logger.debug("TODO: Figure out format for command switchmode.") # TODO: switchmode, see iEast docs
        raise NotImplementedError("Setting player_mode is not implemented yet")

    def player_status(self):
        self._logger.info("Retrieving player status (e.g., play, pause, etc.)...")
        return self._player_info().get('status')

    ''' Player Commands '''

    def play(self, uri=""):
        """Start playback of current media""" # TODO: Need to remove colon if no uri?  Also, accept playlist?
        self._logger.info("Beginning playback"+((" of '"+str(uri)+"'") if uri else "")+"...")
        return self._send("setPlayerCmd:play:"+str(uri)).content.decode("utf-8")

    def pause(self):
        """Pause playback of current media"""
        self._logger.info("Pausing playback...")
        return self._send("setPlayerCmd:pause").content.decode("utf-8")

    def resume(self):
        """Resume playback of current media"""
        self._logger.info("Resuming playback...")
        return self._send("setPlayerCmd:resume").content.decode("utf-8")

    def stop(self):
        """Stop playback of current media"""
        self._logger.info("Stop playback...")
        return self._send("setPlayerCmd:stop").content.decode("utf-8")

    def previous(self):
        """Skip backward to previous track"""
        self._logger.info("Skipping backward to previous media track...")
        return self._send("setPlayerCmd:prev").content.decode("utf-8")

    def next(self):
        """Skip forward to next track"""
        self._logger.info("Skipping forward to next media track...")
        return self._send("setPlayerCmd:next").content.decode("utf-8")

    def seek(self, val):
        """Move to provided time in seconds in media"""
        self._logger.info("Seeking to '" + str(val) + "' second mark in media...")
        return self._position(int(math.floor(float(val)*1000)))

    def back(self, val=10):
        """Rewind playback by given seconds, default 10"""
        self._logger.info("Rewinding playback by '" + str(val) + "' seconds...")
        return self._position(int(self._position() - int(math.floor(float(val)*1000))))

    def forward(self, val=10):
        """Fast-forward playback by given seconds, default 10"""
        self._logger.info("Fast-forwarding playback by '" + str(val) + "' seconds...")
        return self._position(int(self._position() + int(math.floor(float(val)*1000))))

    def _seek(self, val):
        """Internal method to move to provided second mark in media"""
        totlen_ms = int(self._length())
        newpos_ms = int(math.floor(float(val)*1000))
        newpos_ms = max(0, min(totlen_ms, newpos_ms))
        newpos = math.floor(newpos_ms/1000)
        self._logger.debug("Seeking to " + str(newpos) + " second mark in media "+
                           "(position "+str(newpos_ms)+" of "+str(totlen_ms)+")...")
        return self._send("setPlayerCmd:seek:"+str(newpos)).content.decode("utf-8")

    ''' Shuffle and Repeat '''

    def _loop(self, mode=None):
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

    def shuffle(self, value=None):
        """Get or set the shuffle--either on/1/True to turn shuffle on, otherwise turn shuffle off"""
        if value is None:
            self._logger.info("Retrieving shuffle setting...")
            return self._loop().split(':')[3]
        self._logger.info("Setting shuffle to '"+str(value)+"'")
        shuffle = "off" if (isinstance(value, str) and (value == "off" or value == "0")) or not value else "on"
        repeat = self._loop().split(':')[1]
        return self._loop("repeat:"+repeat+":shuffle:"+shuffle)

    def repeat(self, value=None):
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

    def title(self):
        self._logger.info("Retrieving current media title...")
        return self._dehexify(self._player_info().get('Title'))

    def album(self):
        self._logger.info("Retrieving current media album...")
        return self._dehexify(self._player_info().get('Album'))

    def artist(self):
        self._logger.info("Retrieving current media artist...")
        return self._dehexify(self._player_info().get('Artist'))

    def position(self, newpos_ms=None):
        if newpos_ms is None:
            self._logger.info("Retrieving player's current position in media...")
        else:
            self._logger.info("Setting player's position in media to "+str(newpos_ms)+"...")
        return self._position(newpos_ms)

    def _position(self, newpos_ms=None):
        if newpos_ms is None:
            return int(self._player_info().get('curpos'))
        self._logger.debug("Checking total media length to ensure new position is not past the end of the media...")
        totlen_ms = int(self._length())
        newpos_ms = max(0, min(totlen_ms, int(newpos_ms)))
        newpos = math.floor(newpos_ms / 1000)
        self._logger.debug("Setting player media position to "+str(newpos_ms)+" (of "+str(totlen_ms)+" ms)...")
        return self._send("setPlayerCmd:seek:"+str(newpos)).content.decode("utf-8")

    def length(self):
        self._logger.info("Retrieving total length of current media...")
        return self._length()

    def _length(self):
        return int(self._player_info().get('totlen'))

    ''' Volume Control '''

    def volume(self, value=None):
        """Get or set the volume to an absolute value between 0 and 100 or a relative value -100 to +100"""
        if value is None:
            self._logger.info("Retrieving device volume...")
            return self._volume()
        self._logger.info("Setting volume '"+str(value)+"'...")
        return self._volume(value)

    def _volume(self, value=None):
        """Internal method to get/set volume to an absolute value between 0 and 100 or a relative value -100 to +100"""
        if value is None:
            return int(self._player_info().get("vol"))
        try:
            if isinstance(value, str) and value.startswith('+'):
                new_volume = min(100, self._volume()+int(value[1:]))
                self._logger.debug("Increasing volume "+str(value)+" to "+str(new_volume))
            elif isinstance(value, str) and value.startswith('-'):
                new_volume = max(0, self._volume()-int(value[1:]))
                self._logger.debug("Decreasing volume "+str(value)+" to "+str(new_volume))
            else:
                new_volume = min(100, max(0, int(value)))
                self._logger.debug("Setting volume to " + str(int(new_volume)))
        except:
            raise AttributeError("Volume must be between 0 and 100 or -100 to +100, inclusive, not '"+str(value)+"'")
        response = self._send("setPlayerCmd:vol:" + str(new_volume))
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to set volume to '"+str(new_volume)+"'")
        return response.content.decode("utf-8")

    def volume_up(self, value=5):
        """Increase volume by given integer amount, defaults to plus 5"""
        self.volume("+"+str(value))
        return "OK"

    def volume_down(self, value=5):
        """Decrease volume by given integer amount, defaults to minus 5"""
        self.volume("-"+str(value))
        return "OK"

    def mute(self, value=None):
        """Get or set the muting state. 'off' or falsy values turn muting off, otherwise muting is turned on."""
        if value is None:
            self._logger.info("Retrieving state of muting function...")
            return int(self._player_info().get("mute")) == 1
        if not value or (isinstance(value, str) and (value == '0' or value == 'off')):
            return self.mute_off()
        return self.mute_on()

    def mute_on(self):
        """Mute the device"""
        self._logger.info("Turning muting on")
        return self._send("setPlayerCmd:mute:1").content.decode("utf-8")

    def mute_off(self):
        """Unmute the device"""
        self._logger.info("Turning muting off")
        return self._send("setPlayerCmd:mute:0").content.decode("utf-8")

    ''' Source Control '''

    def preset(self, number, uri=None):
        raise NotImplementedError("Presets not implemented yet")

    def playlist(self, uri=None):
        raise NotImplementedError("Setting playlist not implemented yet")

    # See also player_mode, is related to sources



    ''' Equalizer Control '''

    def equalizer(self, mode=None):
        """Get or set the equalizer mode"""
        if mode is None:
            self._logger.info("Retrieving current equalizer setting...")
            inverse_eq_modes = {v: k for k, v in self._equalizer_modes.items()}
            value = self._send("getEqualizer").json()
            try:
                mode = inverse_eq_modes[value]
            except KeyError:
                raise AttributeError("Received unknown equalizer mode value '"+str(value)+"'")
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

    def equalizer_modes(self):
        """Returns the allowed equalizer modes along with their mapped values"""
        return self._equalizer_modes

    ''' Voice Prompts & Jingles '''

    def prompt_on(self):
        """Enable voice prompts and notifications"""
        self._logger.info("Turning voice prompts on...")
        response = self._send("PromptEnable")
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to enable prompts: Status code="+str(response.status_code))
        return response.content.decode("utf-8")

    def prompt_off(self):
        """Disable voice prompts and notifications"""
        self._logger.info("Turning voice prompts off...")
        response = self._send("PromptDisable")
        if response.status_code != 200:
            raise linkplayctl.APIException("Failed to disable prompts: Status code="+str(response.status_code))
        return response.content.decode("utf-8")

    def prompt_language(self, value=None):
        """Set the prompt language [NOT IMPLEMENTED]"""  # TODO: ToHex?
        self._logger.info("Setting voice prompts language... [NOT IMPLEMENTED]")
        raise NotImplementedError("Command 'prompt_language' is not implemented yet")

    ''' Firmware Updating '''

    def firmware_version(self):
        """Get the current firmware version"""
        self._logger.info("Retrieving current firmware version")
        return self._device_info().get("firmware")

    def firmware_update_search(self):
        """Initiate a non-blocking search for new firmware"""
        self._logger.info("Starting firmware update search...")
        return self._send("getMvRemoteUpdateStartCheck").content.decode("utf-8")

    def firmware_update_available(self):
        self._logger.info("Retrieving firmware update availability...")
        return self._send("getMvRemoteUpdateStatus").json()

    def firmware_update_version(self):
        self._logger.info("Retrieving firmware update version...")
        return self._device_info().get("NewVer")

    ''' Multi-Room Setup '''

    def multiroom_list(self):
        self._logger.info("Retrieving list of multiroom group slaves")
        return self._send("multiroom:getSlaveList").json()

    def multiroom_remove(self, ip):
        self._logger.info("Removing '"+str(ip)+"' from list of multiroom slaves")
        return self._send("multiroom:SlaveKickout:"+str(ip)).content.decode("utf-8")

    def multiroom_hide(self, ip):
        self._logger.info("Hiding multiroom slave '" + str(ip) + "' from network list")
        return self._send("multiroom:SlaveMask:"+str(ip)).content.decode("utf-8")

    def multiroom_show(self, ip):
        self._logger.info("Unhiding multiroom slave '" + str(ip) + "' from network list")
        return self._send("multiroom:SlaveUnMask:"+str(ip)).content.decode("utf-8")

    def multiroom_off(self):
        self._logger.info("Tearing down the current multiroom group...")
        return self._send("multiroom:Ungroup").content.decode("utf-8")

    ''' Internal Methods '''

    def _url(self, command):
        """Internal method to construct url fragments from provided command"""
        return "http://" + self._address + "/httpapi.asp?command=" + command

    def _send(self, command):
        """Internal method to send raw fragments to the device"""
        fragment = self._url(command)
        self._logger.debug("Requesting '"+fragment+"'...")
        t0 = time.time()
        try:
            if not self._session:
                self._session = requests.session()
            response = self._session.get(fragment, timeout=30)
            self.api_status_code = response.status_code
            elapsed = round((time.time()-t0)*1000, 1)
            self._logger.debug("Received response from device in "+str(elapsed)+"ms"+
                               " with status code '"+str(self.api_status_code)+"'")
            return response
        except requests.exceptions.RequestException as e:
            raise linkplayctl.ConnectionException("Could not connect to '" + str(self._address) + "': " + str(e))

    def _dehexify(self, hex_string):
        try:
            return bytearray.fromhex(hex_string).decode()
        except ValueError:
            return hex_string

    def _hexify(self, string):
        try:
            return " ".join("{:02x}".format(c) for c in string.encode())
        except ValueError:
            return string
