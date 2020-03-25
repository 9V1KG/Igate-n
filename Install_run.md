
# Install and build from Scratch

This script will build Ygaten from scratch.
New
  - Python Env
  - Code Base
  - Modules

If would make a good base for a Docker image.


# Installing 

These are the steps to install this project.

```
#!/bin/bash

cd 
#Clean Build Take care this will not ask for permission
rm -Rf test_install
mkdir test_install
cd test_install
# New Python Virtual Env
python3 -m venv ~/test_install/pe38
source ~/test_install/pe38/bin/activate
# Lets check we are using the correct python
echo $"which python3"

# Hopefully that looks ok 
# Time to get the git repo
cd
rm -Rf YaesuTest
mkdir YaesuTest && cd YaesuTest
git clone https://github.com/9V1KG/Igate-n.git
cd IGate-n	
python setup.py install
```


# Run with default settings

We need to activate the python Env (the one we just created), if you create a new shell..


	source ~/test_install/pe38/bin/activate


As IGaten is now installed... 
Lets run it.... We can run it directly as it is a Module...

    cd ~/YaesuTest/Igate-n
	python3 -m  IGaten


*Note this actually runs the __main__.py in the Module.... as we are invoking via a module*


# Alter how it runs ?

Sure, we need to write a custom code to call it. This is one of the reasons it is a good ideal to have sensible defaults in the __init__ method.

So to call it using say DU3TW IGaten machine it would be

```python
from IGaten import YGate, Color
ygate = Ygate def __init__(
        self,
        HOST="rotate.aprs2.net.co.uk",
        PORT=14580,
        USER="Du3TW-10",
        PASS="Secret",
        LAT=(15, 20.09, "N"),
        LON=(120, 3.07, "E"),
        BCNTXT="IGate RF-IS 144.39 - 73",
        BEACON=900.0,
        SERIAL="/dev/tty.usbserial-A7004VW8",
    ):
 ygate.start()
```

Of course as it is your code-base, you could always set these values as a default rather than typing code.

There is another solution to this (not implemented), which would require the use of a Config file (Yaml, Json etc). We you to start to manage 4 or upwards IGates this would be a less painful manner to go I think.






