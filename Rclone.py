import logging
import re
import os
import pexpect
import sys
import hashlib


class Rclone:
    rcloneLogFilePath = None
    bash = None

    def __init__(self, rcloneLogFilePath=None):

        self.rcloneLogFilePath = rcloneLogFilePath
        self.bash = pexpect.spawn("/bin/bash", echo=False)

        if self.rcloneLogFilePath is not None:
            self.bash.logfile = open(rcloneLogFilePath, 'wb')

        logging.info("Rclone has been called")

    def logBashToConsole(self, bool):
        if (bool == True):
            self.bash.logfile = sys.stdout.buffer

    def transferSingleFileToRemoteRoot(self, rcloneSourceFile, rcloneRemote, verifyUpload=False, removeSourceFile=False):

        rcloneSourceFileName = rcloneSourceFile

        if rcloneSourceFileName.__contains__("/"):
            rcloneSourceFileName = rcloneSourceFileName.split("/")[-1]

        rcloneSourceFileName = re.sub('"', "", rcloneSourceFileName)
        rcloneSourceFileName = '"' + rcloneSourceFileName + '"'

        logging.info("\tStarting transfer of " + rcloneSourceFile + " to " + rcloneRemote + rcloneSourceFileName)

        self.bash.sendline(
            f"rclone copyto {rcloneSourceFile} {rcloneRemote}{rcloneSourceFileName} -P ; echo RCLONE FINISHED WITH STATUS $?")

        while True:

            result = self.bash.expect(["Transferring:\s*\*\s*", "RCLONE FINISHED WITH STATUS", pexpect.TIMEOUT])

            if result == 0:
                transferProgress = re.search("Transferred:\W*(.*)\n", self.bash.readline().decode("utf-8"))[1]
                logging.info("\t" * 2 + rcloneSourceFileName + ":" + transferProgress)
            elif result == 1:
                logging.debug("\tFinished uploading")
                logging.debug("\t\tSummary:\n" + self.bash.before.decode("utf-8"))
                exitStatus = self.bash.readline().decode("utf-8").strip()

                if exitStatus == "0":
                    logging.info("\tGdrive upload finished successfully")

                    if verifyUpload:
                        logging.info("\t"*2 + "Will start verification of upload")
                        verifyResult = self.verifyUploadedFile(rcloneSourceFile, rcloneRemote + rcloneSourceFileName)

                        if verifyResult:
                            logging.info("\t" * 3 + "Verification was successful")

                            if removeSourceFile:
                                logging.info("\t"*2 + "Removing source file")
                                os.remove(rcloneSourceFile)
                                if os.path.isfile(rcloneSourceFile):
                                    logging.warning("\t"*3 + "Failed to remove source file:" + rcloneSourceFile)
                                else:
                                    logging.info("\t" * 3 + "Source file was removed:" + rcloneSourceFile)

                            return True
                        else:
                            logging.error("\t" * 3 + "Verification of upload failed")
                            logging.error("\t" * 4 + "Local file:" + rcloneSourceFile)
                            logging.error("\t" * 4 + "Remote file:" +  rcloneRemote + rcloneSourceFileName)
                            return False
                    else:
                        if removeSourceFile:
                            logging.info("\t" * 2 + "Removing source file")
                            os.remove(rcloneSourceFile)
                            if os.path.isfile(rcloneSourceFile):
                                logging.warning("\t" * 3 + "Failed to remove source file:" + rcloneSourceFile)
                            else:
                                logging.info("\t" * 3 + "Source file was removed:" + rcloneSourceFile)
                        return True
                else:
                    logging.error("\tGdrive upload finished with error status:" + exitStatus)
                    sys.exit(exitStatus)

            elif result == 2:
                logging.error("\tGdrive upload timed out")
                sys.exit(1)

    def verifyUploadedFile(self, rcloneSourceFile, rcloneRemoteFile):

        logging.info("Verifying successful upload of files")
        logging.info("\tLocal file:" + rcloneSourceFile)
        logging.info("\tRemote file:" + rcloneRemoteFile)

        md5 = hashlib.md5()

        with open(rcloneSourceFile, 'rb') as f:
            while True:
                data = f.read(65536)
                if not data:
                    break
                md5.update(data)

        localHash = md5.hexdigest()
        remoteHash = ""
        logging.debug("\t" * 2 + "Local file MD5 hash:" + localHash)

        self.bash.sendline("rclone hashsum MD5 " + rcloneRemoteFile + "; echo HASHDONE")

        result = self.bash.expect(["HASHDONE", pexpect.TIMEOUT])

        if result == 0:

            fileName = os.path.basename(rcloneSourceFile).replace(".", "\.")
            bashOutput = self.bash.before.decode("utf-8")
            remoteHash = re.search("(\w*)\W*" + fileName, bashOutput)[1]
            logging.debug("\tRemote file MD5 hash:" + remoteHash)
        else:
            bashOutput = self.bash.read_nonblocking(size=500, timeout=1)
            logging.error("\tCould not determine hash of remote file, got:" + bashOutput)
            sys.exit(1)

        if (remoteHash == localHash):
            logging.info("\tVerification was successful, the hashes match")
            return True
        else:
            logging.warning("\tVerification was unsuccessful, the hashes dont match")
            return False
