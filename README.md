
# Linkplayctl

A simple shell & python client for controlling Linkplay devices.

Linkplay is a whitelabel manufacturer that powers a number of brands of wireless speakers and receivers, including:
* Muzo Cobblestone
* GGMM E2, E3, E5, M4, M3, etc.
* Riversong/ANEWISH
* iEast SoundStream & StreamAmp
* Everything listed at http://linkplay.com/featured-products/

Linkplayctl can control these devices (and many more).  Linkplayctl can remotely reboot devices, start and stop playback, adjust volume, get hardware and player information, turn off annoying jingles, etc.  



### Installation

Linkplayctl requires Python 3 and these modules:
* requests

If your environment does not have the requests module already, the simplest way to acquire it is to install pip.  On Ubuntu, try
```sudo apt-get install python3-pip```  or similar.

To get the linkplayctl module, download from github or clone:
```git clone ```


### Example Usage

Python:

```
import Linkplayctl

client = Linkplayctl.Client("192.168.1.55") # Address of the linkplay device
client.reboot()                             # Reboot device
client.play("http://path/to/playlist")      # Play streaming playlist
client.volume_up()                          # Increase volume by one step
client.equalizer("jazz")                    # Set the equalizer mode to jazzy
client.rewind(10)                           # Rewind playback by 10 seconds
...

```

Command Line:

```
$> bin/linkplayctl 192.168.1.55 reboot
OK
$> bin/linkplayctl 192.168.1.55 play "http://path/to/playlist"
OK
$> bin/linkplayctl 192.168.1.55 volume up
OK
$> bin/linkplayctl 192.168.1.55 equalizer jazz
OK
$> bin/linkplayctl 192.168.1.55 rewind 10
OK
...

```

To date, Linkplayctl implements about 70 commands, which are implemented and documented as methods in the Client class.  





### Acknowledgments

* https://github.com/AndersFluur/IEastMediaRoom for API info
* https://marketplace.fibaro.com/profiles/albert-walczyk for API info



