# 3dWiFiSend

This was a significant re-write from the original ( found at: https://github.com/yandreev3/3dWiFiSend)

The focus was on being able to send .gx and .gcode files to a FlashForge printer and print them.

Needs some work around error checking, response checking and to figure out how to actually get a file list from the FlashForge disk and sd card.

TODO: retrofit all routines that write to the network with responseOK()
TODO: Really need some proper error & exception checking all the way thorugh
TODO: Add code to confirm that the file was received and closed properly
TODO: Figure out how file listing works on FF Printers.
TODO: Make responseOK() this do a more robust response check.

usage: 3DWiFiSendFile.py [-h] [-s] [-l] [-p] [-a HOSTNAME] [filename]

positional arguments:
  filename     Filename of file to send to printer.

optional arguments:
  -h, --help   show this help message and exit
  -s           Print status of the 3D Printer.
  -l           List the files on the printer SD Card.
  -p           Print on completion of file download.
  -a HOSTNAME  Hostname or IP address of printer.


