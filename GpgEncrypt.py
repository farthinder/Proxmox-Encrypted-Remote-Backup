import logging
import subprocess
import sys
import pexpect
import re  # Regex
import datetime
import time


class GpgEncrypt:
    gpgRecipient = None
    gpgOutputDirectory = None
    gpgOutputFileName = None
    gpgSourceDir = None
    gpgInputFilesList = list()
    gpgInputFilesString = ""
    rcloneLogFilePath = None
    bash = None
    fileEncryptTimeout = 300 #What is the maximum amount of time a single file should take to encrypt

    def __init__(self, gpgRecipient, gpgSourceDir, gpgInputFiles, gpgOutputDirectory, gpgOutputFileName, rcloneLogFilePath = None):



        logging.info("GpgEncrypt has been called")

        self.gpgOutputDirectory = gpgOutputDirectory
        self.gpgOutputFileName = gpgOutputFileName
        self.gpgRecipient = gpgRecipient
        self.gpgSourceDir = gpgSourceDir
        self.gpgInputFilesList = gpgInputFiles
        self.rcloneLogFilePath = rcloneLogFilePath

        for index in self.gpgInputFilesList:
            self.gpgInputFilesString += '"' + index + '" '

        logging.debug("\tThe recipient of encrypted data will be:" + gpgRecipient)
        logging.debug("\tThe source directory will be:" + gpgSourceDir)
        logging.debug("\tWill encrypt:" + self.gpgInputFilesString)
        logging.debug("\tThe output dir will be:" + gpgOutputDirectory)
        logging.debug("\tThe output file name will be:" + gpgOutputFileName)


        self.bash = pexpect.spawn("/bin/bash", echo=False)

        if self.rcloneLogFilePath is not None:
            self.bash.logfile = open(rcloneLogFilePath, 'wb')



    def logBashToConsole(self, bool):
        if (bool == True):
            self.bash.logfile = sys.stdout.buffer


    def checkParameters(self):


        logging.debug("\tChecking if gpg recipient ("+ self.gpgRecipient +") cert is installed")

        self.bash.sendline("gpg --list-public-keys " + self.gpgRecipient)
        result = self.bash.expect([self.gpgRecipient, "error reading key: No public key", pexpect.EOF, pexpect.TIMEOUT],
                             timeout=5)

        if result == 0:
            logging.debug("\t\tFound certificate")
        else:
            logging.error("\t\tCould not find certificate")
            sys.exit(1)

        logging.debug("\tChecking if working directory (" + self.gpgSourceDir + ") exists")
        self.bash.sendline("cd " + self.gpgSourceDir)
        self.bash.sendline("echo Current Dir ; pwd")
        self.bash.expect("Current Dir\r\n")

        result = self.bash.expect(
            [re.sub(r"\/$", "", self.gpgSourceDir) + "\r\n", "No such file or directory", pexpect.EOF, pexpect.TIMEOUT],
            timeout=2)
        if result == 0:
            logging.debug("\t\tFound gpgSourceDir")
        elif result == 1:
            logging.error("\tError browsing to gpgSourceDir:" + self.gpgSourceDir + ", No such file or directory")
            sys.exit(1)
        else:
            logging.error("\tError browsing to gpgSourceDir:" + self.gpgSourceDir + ", unexpected output")

        self.bash.expect([".*", pexpect.EOF, pexpect.TIMEOUT], timeout=1)
        #elf.bash.readline()

    def encryptFiles(self):

        logging.info("Starting encryption of files:")




        logging.info("\tWill be placed here:" + self.gpgOutputDirectory + self.gpgOutputFileName)

        gpgCommand = "tar -cv "+self.gpgInputFilesString+" | gpg --output "+self.gpgOutputDirectory + self.gpgOutputFileName+" -e --recipient " + self.gpgRecipient
        gpgCommand = gpgCommand + "; echo Encryption Done"
        logging.debug("\ttar and gpg command:" + gpgCommand)
        logging.info("\tEncrypting files:")


        getFileSizeComment = 'echo -n FILESIZESTART ; stat -c "%s" '+self.gpgOutputDirectory + self.gpgOutputFileName+' | numfmt --to=iec-i --suffix=B --format="%.3f" ; echo FILESIZESTOP'
        lastFileSizeCheck = time.time()
        lastFileSizeString = None


        self.bash.sendline(gpgCommand)

        bashWatchdog = pexpect.spawn("/bin/bash", echo=False)
        #bashWatchdog.logfile = sys.stdout.buffer


        while True:
            result = self.bash.expect(["Encryption Done", "Overwrite\? \(y/N\)","\r\n",  pexpect.TIMEOUT], timeout=1)

            if result == 2:

                logging.info("\t" * 2 + self.bash.before.decode("utf-8"))
            elif result == 0:
                logging.debug("\tFinished encrypting files")
                return {"success": True, "output": self.gpgOutputDirectory + self.gpgOutputFileName}
            elif result == 3:
                #No update on file encryption
                pass
            elif result == 1:
                logging.error("Error encrypting files, destination file already exists:" + self.gpgOutputDirectory + self.gpgOutputFileName)
                logging.error("\t" + self.bash.before.decode("utf-8"))
                sys.exit(1)
            else:
                logging.error("Error encrypting files")
                sys.exit(1)

            if ((time.time() - lastFileSizeCheck) > 5):
                lastFileSizeCheck = time.time()
                bashWatchdog.sendline(getFileSizeComment)
                #resultWatchdog = bashWatchdog.expect(["\d*.\d*B", pexpect.TIMEOUT, pexpect.EOF], timeout=5)
                resultWatchdog = bashWatchdog.expect(["FILESIZESTOP", pexpect.TIMEOUT, pexpect.EOF], timeout=5)

                if resultWatchdog == 0:

                    sizeString = bashWatchdog.before.decode("utf-8")
                    sizeString = re.search("FILESIZESTART(\d*\.\d*\w*B)", sizeString)[1]
                    logging.info("\t"*3+"Current size of encrypted outfile:" + sizeString)

                    if (sizeString == lastFileSizeString):
                        logging.warning("File size is not growing")
                        sys.exit(1)

                    else:
                        lastFileSizeString = sizeString

                else:
                    logging.info("Warning Size:" + bashWatchdog.before.decode("utf-8"))
                    logging.warning("Failed to get size of encrypted file")

