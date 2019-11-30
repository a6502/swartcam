# SwartCam

## Description

This simple Python 3 script allows control of a Raspberry Pi camera by way
of a tiny website running on `http://<ip of pi>:3000/`. This website has 2
buttons:

- Start/Stop Preview

   This starts/stops a full screen preview.

- Start/Stop Streaming

   This starts streaming video from the camera and audio from a usb
   microphone to the rtmp-stream target mentioned in the config file.
   ('swartcam.conf')

This script was created for a rather specific use case, but maybe someone
finds this useful as inspiration.

## Installation

The only non-standard Python3 module required is 'PiCamera'. This should be
already be installed on a standard Raspbian installation, together with
Python3 itself.

## License

MIT License, see the LICENSE file.

## Author

Wieger Opmeer

(No email, if you want to contact me, create an issue on Github)

