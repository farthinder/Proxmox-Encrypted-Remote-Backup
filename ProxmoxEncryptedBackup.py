#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""

    * Prerequisite:
        * rclone setup with a remote
            * Tested with v1.45 and google drive
        * gpg setup with at least a public key for a recipient
        * tar
        * python3
            * The pexpect library needs to be available
		        * python3 -m pip install pexpect
        * ProxmoxEncryptedBackup.py is made executable
            * chmod o+x ProxmoxEncryptedBackup.py


    * Possible Improvements:
        * Handle rclone errors
        * Test rclone with other remotes than gdrive
        * Cleanup
            * Source files
        * Improve getting config from file

    * Implemented Improvments
        * Cleanup
            * jobfiles
            * .enc files
        * Verify uploads with rclone hashsum MD5 gdrive:106-2020_01_02-22_10_33.enc
        *  Start upload immediately after finished encryption of individual file
"""

import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging.handlers import RotatingFileHandler

import GpgEncrypt
import ProxmoxEncryptedBackupSettings as Settings
import ProxmoxEventHandler
import Rclone

# This log handler will print to the console and will show up in the Proxmox GUI when viewing the job.
stdOutHandler = logging.StreamHandler(sys.stdout)
stdOutHandler.setLevel(logging.INFO)
stdOutFormat = logging.Formatter('CryptBackup - %(levelname)s - %(message)s')
stdOutHandler.setFormatter(stdOutFormat)

fileHandler = RotatingFileHandler(filename=Settings.logFile, maxBytes=Settings.logFileSizeMB * 1049000, backupCount=Settings.logFilesToKeep)
fileHandler.setLevel(logging.DEBUG)
fileFormatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler.setFormatter(fileFormatter)

logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger().addHandler(fileHandler)
logging.getLogger().addHandler(stdOutHandler)

logging.info("Encrypted BackupScript called")

if (Settings.runOldJobId is not None):
    eventHandler = ProxmoxEventHandler.ProxmoxEventHandler(Settings.jobFolder, Settings.runOldJobId)
    event = eventHandler.getOldJob()


else:
    eventHandler = ProxmoxEventHandler.ProxmoxEventHandler(Settings.jobFolder)
    event = eventHandler.getPhase()

encryptFilesOutput = []



def encryptFiles(recipient, sourceDirectory, sourceFiles, destinationFolder, destinationFileName):
    gpgEncrypt = GpgEncrypt.GpgEncrypt(
        gpgRecipient=recipient,
        gpgSourceDir=sourceDirectory,
        gpgInputFiles=sourceFiles,
        gpgOutputDirectory=destinationFolder,
        gpgOutputFileName=destinationFileName
    )

    gpgEncrypt.checkParameters()
    encryptionResult = gpgEncrypt.encryptFiles()
    encryptFilesOutput.append(encryptionResult)
    return encryptionResult

def uploadFile(file, remoteName):
        rclone = Rclone.Rclone()
        uploadResult = rclone.transferSingleFileToRemoteRoot(file, remoteName,
                                                             verifyUpload=Settings.rcloneVerifyUploads,
                                                             removeSourceFile=Settings.rcloneRemoveSourceFile)
        if uploadResult:
            logging.info("Finished upload of " + file)
        else:
            logging.error("Error uploading " + file + " could not verify has")


def encryptAndUploadFiles(recipient, sourceDirectory, sourceFiles, destinationFolder, destinationFileName, remoteName):
    encryptionResult = encryptFiles(
        recipient=recipient,
        sourceDirectory=sourceDirectory,
        sourceFiles=sourceFiles,
        destinationFolder=destinationFolder,
        destinationFileName=destinationFileName
    )

    if (encryptionResult["success"] == True):
        logging.info("\tFiles have been successfully encrypted and placed here: " + str(encryptionResult["output"]))
        logging.info("\t\tStarting upload to " + Settings.rcloneRemoteName)
        uploadFile(file=encryptionResult["output"], remoteName=Settings.rcloneRemoteName)
    else:
        logging.error("There was an error encrypting " + sourceFiles)


def cleanupJobFiles():
    logging.info("Preparing to remove old job files from:" + Settings.jobFolder)

    now = time.time()

    for fileName in os.listdir(Settings.jobFolder):
        logging.debug("\tEvaluating job file:" + fileName)

        if os.path.splitext(fileName)[1] == ".job":

            if now > (os.stat(os.path.join(Settings.jobFolder, fileName)).st_mtime + Settings.keepJobsForDays * 86400):
                logging.debug("\t" * 2 + "File will be removed")
                os.remove(os.path.join(Settings.jobFolder, fileName))
            else:
                logging.debug("\t" * 2 + "File will not be removed")

        else:
            logging.debug("\t" * 2 + "Skipping the file, the extension is not .job")


if (Settings.runOldJobId is not None or event == "job-end"):
    logging.info("The backup job has ended successfully, will prepare to encrypt")
    filesToEncrypt = eventHandler.getFilesFromPhase("backup-end")
    pathToFiles = eventHandler.jobinfo["job-end"]["dumpdir"]
    logging.debug("\tWill encrypt files:" + str(filesToEncrypt))
    logging.debug("\tFrom path:" + pathToFiles)

    threadFutures = []
    threadPool = ThreadPoolExecutor(max_workers=Settings.threads)
    for index in filesToEncrypt:
        outputFilename = re.search("vzdump-(?:qemu|lxc)-(.*)\.\w*?$", index["tarfile"])[1]
        outputFilename += ".enc"
        threadFutures.append(
            threadPool.submit(encryptAndUploadFiles,
                              recipient=Settings.gpgRecipient,
                              sourceDirectory=pathToFiles,
                              sourceFiles=[index["tarfile"], index["logfile"]],
                              destinationFolder=Settings.gpgOutputDirectory,
                              destinationFileName=outputFilename,
                              remoteName=Settings.rcloneRemoteName
                              )
        )

    for x in as_completed(threadFutures):
        result = x.result()
        if result is not None:
            logging.info(str(result))

    for job in threadFutures:
        if job.exception() is not None:
            logging.debug("error::")
            job.result()
            sys.exit(1)


    cleanupJobFiles()
