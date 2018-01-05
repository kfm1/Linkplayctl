
# Linkplayctl

A simple shell & python client for controlling Linkplay devices.

Linkplay is a whitelabel manufacturer that powers a number of brands of wireless speakers and receivers, including:
* Muzo Cobblestone
* GGMM E2, E3, E5, M4, M3, etc.
* Riverson/ANEWISH
* Everything listed at http://linkplay.com/featured-products/

Linkplayctl can control these devices (and many more).



### Installation

Linkplayctl requires Python 3 and these modules:
* requests

If your environment does not have the requests module, you can acquire it by installing pip.  On Ubuntu, try
```sudo apt-get install python3-pip```  or similar.


### Usage

Python:

```
import Linkplayctl

client = Linkplayctl.Client("192.168.1.0")  # Address of the linkplay device
client.reboot()             # Reboot device
client.volume_up()          # Increase volume by one step
client.equalizer("jazz")    # Set the equalizer mode to jazzy
...

```

Command Line:

```
$> bin/linkplayctl 192.168.1.0 reboot
OK
$> bin/linkplayctl 192.168.1.0 volume up
OK
$> bin/linkplayctl 192.168.1.0 equalizer jazz
OK
...

```



### Acknowledgments

* https://github.com/AndersFluur/IEastMediaRoom for the API



