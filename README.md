
# Linkplayctl

A simple shell & python client for controlling wireless speakers and receivers.

Linkplay is a whitelabel manufacturer that powers a number of brands of wireless speakers and receivers, including:
* Muzo Cobblestone
* GGMM E2, E3, E5, M4, M3, etc.
* Riversong/ANEWISH
* iEast SoundStream & StreamAmp
* Everything listed at http://linkplay.com/featured-products/

Linkplayctl can control these devices (and many more).  Linkplayctl can remotely reboot devices, start and stop playback, adjust volume, get hardware and player information, turn off annoying jingles, etc.  



### Installation

Linkplayctl requires Python 3 and the following module:
* requests

If your environment does not have the requests module already, the simplest way to acquire it is to install pip.  On Ubuntu, try
```sudo apt-get install python3-pip```  or similar.

To get the linkplayctl module, download from github or clone:
```git clone https://github.com/kfm1/Linkplayctl.git```


### Example Usage

Python:

```
import Linkplayctl

client = Linkplayctl.Client("192.168.1.55") # Address of the linkplay device
client.reboot()                             # Reboot device
client.play("http://path/to/playlist")      # Play streaming playlist
client.volume(100)                          # Set volume to maximum
client.equalizer("jazz")                    # Set the equalizer mode to jazzy
client.rewind(10)                           # Rewind playback by 10 seconds
client.volume_down()                        # Decrease volume by one step (~5%)
client.reboot_quiet()                       # Reboot without startup jingle
client.volume()                             # Get current volume
...

```

Command Line:

```
$> bin/linkplayctl 192.168.1.55 reboot
OK
$> bin/linkplayctl 192.168.1.55 play "http://path/to/playlist"
OK
$> bin/linkplayctl 192.168.1.55 volume 100
OK
$> bin/linkplayctl 192.168.1.55 equalizer jazz
OK
$> bin/linkplayctl 192.168.1.55 rewind 10
OK
$> bin/linkplayctl 192.168.1.55 volume down
OK
$> bin/linkplayctl 192.168.1.55 reboot quiet
OK
$> bin/linkplayctl 192.168.1.55 volume
95
...

```

To date, Linkplayctl implements about 70 commands, which are implemented and documented as methods in the Client class.  





### Acknowledgments

* https://github.com/AndersFluur/IEastMediaRoom for API info
* https://marketplace.fibaro.com/profiles/albert-walczyk for API info



