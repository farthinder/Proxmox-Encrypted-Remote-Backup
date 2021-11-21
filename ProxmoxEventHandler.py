import sys
import argparse
import logging
import time
import os
import json
import datetime


class ProxmoxEventHandler:
    args = None
    jobinfo = {}
    jobFilePath = ""

    def __init__(self, jobFolder, jobId = None):

        if (jobId == None):
            self.jobinfo = {'ppid': str(os.getppid())}
        else:
            self.jobinfo = {"ppid": jobId}

        self.jobFilePath = jobFolder + self.jobinfo['ppid'] + ".job"
        logging.info("Job File:" + self.jobFilePath)
        logging.debug("Raw Input parameters:" + ",".join(sys.argv))


        if not os.path.exists(jobFolder):
            logging.debug("Job folder does not already exist, creating it.")
            os.makedirs(jobFolder)

        parser = argparse.ArgumentParser()
        parser.add_argument("phase", help="backup phase")
        parser.add_argument("attributes", help="backup attributes mode and vmid", nargs='*')
        self.args = parser.parse_args()

        logging.info("Phase:" + self.args.phase)

        self.jobinfo[self.args.phase] = []



    '''
    prior to this __init__ must have been called with the jobId parameter
    '''
    def getOldJob(self):
        if os.path.isfile(self.jobFilePath) is False:
            logging.error("Existing job file not found: " + self.jobFilePath)
            sys.exit(1)

        with open(self.jobFilePath) as json_file:
            logging.info("Parsing existing job file:" + self.jobFilePath)
            self.jobinfo = json.load(json_file)

    '''
    Gets script input paramaters and enviromental variables and adds to job file.
    Returns the current phase as a string
    '''
    def getPhase(self):


        if self.args.phase == 'job-start':


            dumpdir = os.environ["DUMPDIR"]
            storeid = os.environ["STOREID"]

            self.jobinfo[self.args.phase].append(
                {
                    'dumpdir': dumpdir,
                    'storeid': storeid
                }
            )

            logging.debug("Environment Variables:" + str(self.jobinfo[self.args.phase]))

            if os.path.isfile(self.jobFilePath):
                logging.error("Existing job file found: " + self.jobFilePath)
                sys.exit(1)

            with open(self.jobFilePath, 'w') as outfile:
                logging.info("Creating new job file:" + self.jobFilePath)
                json.dump(self.jobinfo, outfile)

            return self.args.phase

        elif self.args.phase == 'job-end':

            dumpdir = os.environ["DUMPDIR"]
            storeid = os.environ["STOREID"]

            if os.path.isfile(self.jobFilePath) is False:
                logging.error("Existing job file not found: " + self.jobFilePath)
                sys.exit(1)

            with open(self.jobFilePath) as json_file:
                logging.info("Parsing existing job file:" + self.jobFilePath)
                self.jobinfo = json.load(json_file)


            self.jobinfo[self.args.phase] = {
                    'dumpdir': dumpdir,
                    'storeid': storeid
                }


            logging.debug("Environment Variables:" + str(self.jobinfo[self.args.phase]))

            with open(self.jobFilePath, 'w') as outfile:
                logging.info("Updating existing job file:" + self.jobFilePath)
                json.dump(self.jobinfo, outfile)

            return self.args.phase

        elif self.args.phase == 'job-abort':

            dumpdir = os.environ["DUMPDIR"]
            storeid = os.environ["STOREID"]

            if os.path.isfile(self.jobFilePath) is False:
                logging.warning("Existing job file not found: " + self.jobFilePath)

            with open(self.jobFilePath) as json_file:
                logging.info("Parsing existing job file:" + self.jobFilePath)
                self.jobinfo = json.load(json_file)

            self.jobinfo[self.args.phase] = []
            self.jobinfo[self.args.phase].append(
                {
                    'dumpdir': dumpdir,
                    'storeid': storeid
                }
            )

            logging.debug("Environment Variables:" + str(self.jobinfo[self.args.phase]))

            with open(self.jobFilePath, 'w') as outfile:
                logging.info("Updating job file:" + self.jobFilePath)
                json.dump(self.jobinfo, outfile)

            return self.args.phase

        elif (self.args.phase == 'backup-start' or
              self.args.phase == 'backup-end' or
              self.args.phase == 'backup-abort' or
              self.args.phase == 'log-end' or
              self.args.phase == 'pre-stop' or
              self.args.phase == 'post-restart' or
              self.args.phase == 'pre-restart'):

            vmid = self.args.attributes.pop()
            mode = self.args.attributes.pop()

            vmtype = os.environ["VMTYPE"]  # openvz/qemu
            dumpdir = os.environ["DUMPDIR"]
            storeid = os.environ["STOREID"]
            hostname = os.environ["HOSTNAME"]
            # TARGET is only available in phase 'backup-end'
            targetfile = os.environ["TARGET"] #Contains the full path to the current VM backup file
            # logfile is only available in phase 'log-end'
            logfile = os.environ["LOGFILE"]

            if os.path.isfile(self.jobFilePath) is False:
                logging.error("Existing job file not found: " + self.jobFilePath)
                sys.exit(1)

            with open(self.jobFilePath) as json_file:
                logging.info("Parsing existing job file:" + self.jobFilePath)
                self.jobinfo = json.load(json_file)

            if self.args.phase not in self.jobinfo:
                self.jobinfo[self.args.phase] = {}

            self.jobinfo[self.args.phase][vmid] = {
                'vmid': vmid,
                'vmtype': vmtype,
                'dumpdir': dumpdir,
                'storeid': storeid,
                'hostname': hostname,
                'targetfile': targetfile,
                'logfile': logfile,
                'mode': mode
            }

            logging.debug("Environment Variables:" + str(self.jobinfo[self.args.phase][vmid]))

            with open(self.jobFilePath, 'w') as outfile:
                logging.info("Updating existing job file:" + self.jobFilePath)
                json.dump(self.jobinfo, outfile)

            return self.args.phase

        else:
            raise Exception("got unknown phase '%s'" % phase)

    '''

    Returns a an array with dics with quoted targetfile and logfile elements:
        [
            {targetfile: "vzdump-qemu-107-2019_12_29-23_22_54.vma",logfile: "vzdump-qemu-107-2019_12_29-23_22_54.log"},
            {targetfile: "vzdump-qemu-108-2019_12_29-23_22_54.vma",logfile: "vzdump-qemu-108-2019_12_29-23_22_54.log"},
        ]
    '''
    def getFilesFromPhase(self, phase):
        logging.debug("Gathering files from phase: " + phase)
        filePaths = []

        for x in self.jobinfo[phase]:
            targetfile = self.jobinfo[phase][x]["targetfile"].split("/")[-1]
            logfile =  self.jobinfo[phase][x]["logfile"].split("/")[-1]

            filePaths.append({"targetfile" : targetfile, "logfile" : logfile})

        logging.debug("Got " + str(len(filePaths) * 2) + " files")

        return filePaths
