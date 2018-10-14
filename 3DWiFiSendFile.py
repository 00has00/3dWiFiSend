#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import socket
import binascii
import argparse
from pathlib import Path

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)


class Print3D:

    # TODO: retrofit all routines that write to the network with responseOK()
    # TODO: Really need some proper error & exception checking all the way thorugh

    CMD_STARTWRITE_SD = "M28 "
    CMD_ENDWRITE_SD = "~M29"
    CMD_GETFILELIST = "~M20 "
    CMD_STARTPRINT = "~M27"
    CMD_SETSDFILE = "~M23 "
    CMD_STATUS = "~M115\x0d\x0a"
    CMD_INIT = "~M601 S1\x0d\x0a"
    CMD_TERM = "\x0d\x0a"
    CMD_RELEASE = "~M602\x0d\x0a"
    CHUNK_HEADER1 = bytes([0x5a, 0x5a, 0xa5, 0xa5])
    CHUNK_HEADER2 = bytes([0x00, 0x00, 0x10, 0x00])
    RESPONSE_OK = 'ok\x0d\x0a'

    def __init__(self):
        self.ipaddr = ''
        self.port = 8899
        self.name = 'undefined'
        self.PKTSIZE = 1460
        self.BUFSIZE = 4113
        self.RECVBUF = 1024
        self.fileName = ''
        self.baseFilename = ''
        self.dirPath = ''
        self.sdPath = '0:/user/'
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._file_encode = 'utf-8'

    def __str__(self):
        s = ('Device addr:' + self.ipaddr + '==' + self.name)
        return s

    def connect(self, hostname='localhost'):
        try:
            self.ipaddr = socket.gethostbyname(hostname)
            logger.info("Connected to host: {0}, IP: {1}".format(hostname, self.ipaddr))
            self.sock.connect((self.ipaddr, self.port))
            self.sock.send(bytes(self.CMD_INIT, self._file_encode))
            msg = self.responseWait()
            logger.debug(msg)
            if not self.responseOK(msg):
                logger.error("connect: Failed to control printer.")
                return False
            return True

        except Exception as dd:
            print(dd)
            # print("Failed TCP connection to Server!")
            exit(-1)

        return

    def release(self):
        cmd = self.CMD_RELEASE
        self.sock.send(self.encodeCmd(cmd))
        msg = self.responseWait()
        logger.info(msg)

    def encodeCmd(self, cmd):
        return cmd.encode(self._file_encode, 'ignore')

    def decodeCmd(self, cmd):
        return cmd.decode(self._file_encode, 'ignore')

    def sendStartWriteSd(self):
        cmd = self.CMD_STARTWRITE_SD + self.fileName
        logger.info("Start write to SD: " + cmd)
        self.sock.send(self.encodeCmd(cmd))
        msg = self.responseWait()
        logger.info("Start write to SD result: " + msg)
        return

    def status(self):
        self.sock.send(bytes(self.CMD_STATUS, self._file_encode))
        msg = self.responseWait()
        logger.debug(msg)
        return msg

    def sendEndWriteSd(self):
        cmd = self.CMD_ENDWRITE_SD + self.CMD_TERM
        logger.info("End write to SD: " + cmd)
        self.sock.send(self.encodeCmd(cmd))
        msg = self.responseWait()
        # TODO: Add code to confirm that the file was received and closed properly
        logger.info("End write to SD result: " + msg)
        return

    def sendGetFileList(self):

        # TODO: Figure out how file listing works on FF Printers.

        cmd = self.CMD_GETFILELIST + self.CMD_TERM
        logger.info("Get List of Files: " + cmd)
        self.sock.send(self.encodeCmd(cmd))
        msg = self.responseWait()
        logger.info("Get list of files result: " + msg)
        return msg

    def sendFileChunk(self, buff, seekPos, chknum):

        # logger.debug("File Position: " + str(seekPos))

        chunkCount = chknum.to_bytes(4,'big')
        myCRC = binascii.crc32(buff).to_bytes(4, 'big')
        dataArray = self.CHUNK_HEADER1 + chunkCount + self.CHUNK_HEADER2 + myCRC + buff
        tmpSize = len(dataArray)

        if tmpSize <= 0:
            return

        self.sock.send(dataArray)
        msg = self.responseWait()
        if not self.responseOK(msg):
            logger.error("Failed to get OK from printer to chunck")
            return -1

        return

    def sendFile(self):

        # TODO: Make sure we aren't printing already before uploading a new file.

        with open(self.fileName, 'rb', buffering=1) as fp:
            # Get File Length
            fp.seek(0, 2)
            filesize = fp.tell()
            fp.seek(0, 0)
            logger.info("Filesize is: " + str(filesize))

            # Announce to the printer that we are sending a file.
            cmd = '~M28 ' + str(filesize) + ' 0:/user/' + self.baseFilename + self.CMD_TERM
            self.sock.send(self.encodeCmd(cmd))
            msg = self.responseWait()
            if not self.responseOK(msg):
                logger.error("Printer failed to accept file")
                exit(-1)

            logger.info("Printer ready to recieve file: " + cmd)
            # Chunk File up into lots of 4092 packets for sending
            # Stick header on each chunk.
            chunkNum = 0
            chunkHeaderLength = len(self.CHUNK_HEADER1) + len(self.CHUNK_HEADER2) + 4
            # Set up progress bar
            self.printProgressBar(0, filesize, prefix='Progress:', suffix='Complete', length=25)
            while True:
                seekPos = fp.tell()
                self.printProgressBar(seekPos, filesize, prefix='Progress:', suffix='Complete', length=25)
                chunk = fp.read(self.BUFSIZE - chunkHeaderLength - 5)
                # logger.debug("Bytes Read from file " + str(len(chunk)))
                if not chunk:
                    break

                if len(chunk) < self.BUFSIZE-chunkHeaderLength-5:
                    logger.debug("Appended \\x00's to make up buffer")
                    chunk += bytearray(self.BUFSIZE-chunkHeaderLength-5-len(chunk))

                self.sendFileChunk(chunk, seekPos, chunkNum)
                chunkNum += 1

        logger.debug("End write SendFile ")
        fp.close()

        self.sendEndWriteSd()

        return

    def sendStartPrint(self):

        # TODO: make sure we aren't already printing before trying to print something new.

        sdFileName = self.sdPath + self.baseFilename
        cmd = self.CMD_SETSDFILE + sdFileName + self.CMD_TERM
        self.sock.send(self.encodeCmd(cmd))
        msg = self.responseWait()
        if self.responseOK(msg):
            logger.debug("startPrint: set sd card filename: " + sdFileName)
        else:
            logger.error("startPrint: failed to set SD card filename: " + sdFileName)
            return False

        cmd = self.CMD_STARTPRINT + self.CMD_TERM
        self.sock.send(self.encodeCmd(cmd))
        msg = self.responseWait()
        if self.responseOK(msg):
            logger.debug("startPrint: successfully started print job")
        else:
            logger.error("startPrint: failed to start print job")
            return False

        return True

    def responseWait(self):
        msg = self.sock.recv(self.RECVBUF)
        return msg.decode(self._file_encode, 'replace')

    def responseOK(self, response):

        # TODO: Make this do a more robust response check.

        logger.debug(response)
        logger.debug(response.endswith((str(self.RESPONSE_OK))))
        if response.endswith(str(self.RESPONSE_OK)):
            logger.debug("Server Response: OK")
            return True
        else:
            logger.debug( "Fuck It. \n'" + response + "'")
            logger.error("Server Response: NOT OK")
            return False

    # Print iterations progress
    def printProgressBar(self, iteration, total, prefix='', suffix='', decimals=0, length=100, fill='█'):
        """
        (Thanks Greenstick@stackoverflow)
        Call in a loop to create terminal progress bar
        @params:
            iteration   - Required  : current iteration (Int)
            total       - Required  : total iterations (Int)
            prefix      - Optional  : prefix string (Str)
            suffix      - Optional  : suffix string (Str)
            decimals    - Optional  : positive number of decimals in percent complete (Int)
            length      - Optional  : character length of bar (Int)
            fill        - Optional  : bar fill character (Str)
        """
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(length * iteration // total)
        bar = fill * filledLength + '-' * (length - filledLength)
        print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end='\r')
        # Print New Line on Complete
        if iteration == total:
            print()


def __Main__():

    # Commands line arguments
    argpar = argparse.ArgumentParser()
    argpar.add_argument('filename', nargs='?', action='store', help='Filename of file to send to printer.')
    argpar.add_argument('-s', action='store_true', help='Print status of the 3D Printer.')
    argpar.add_argument('-l', action='store_true', help='List the files on the printer SD Card.')
    argpar.add_argument('-p', action='store_true', help='Print on completion of file download.')
    argpar.add_argument('-a', dest='hostname', default='10.1.1.129', help='Hostname or IP address of printer.')

    # Create the printer object ready to start recieving variables.
    myobj = Print3D()

    args = argpar.parse_args()

    # Connect to the host
    myobj.connect(args.hostname)

    if args.s:
        status = myobj.status()
        print(status)

    if args.l:
        print(myobj.sendGetFileList())

    if args.filename:
        myFile = Path(args.filename)
        myobj.baseFilename = myFile.name

        if myFile.is_file:
            myFile = Path(args.filename).resolve()
            myobj.fileName = str(myFile)
            print("Sending to printer: " + myobj.fileName)
            myobj.sendFile()

        if args.p:
            myobj.sendStartPrint()
            print("Set to print: " + myobj.baseFilename)


    myobj.release()


if __name__ == '__main__':
    __Main__()