'''

    NOTE! Any folder paths given should end with /

    To apply script edit jobs in  /etc/pve/vzdump.cron
        add to jobs: --script ...../ProxmoxEncryptedBackup.py
'''

runOldJobId = None  # if populated, this existing old job id will be run
# runOldJobId = "20847"  # if populated, this existing old job id will be run, this should only be used if you run ProxmoxEncryptedBackup.py manually.
jobFolder = "/opt/scripting/encryptedRemoteBackup/jobs/"  # A folder that will hold json files with information about ongoing and historic backup jobs
keepJobsForDays = 14  # How many days should old job files be kept. These can be good for troubleshooting but is otherwise of no use.

logFile = '/opt/scripting/encryptedRemoteBackup/output.log'  # The main log file
logFileSizeMB = 5  # Size of the logfile before role-over
logFilesToKeep = 5  # How many log files should be kept before deleting.

gpgRecipient = "farthinder"  # Recipient of the encrypted data. This should match the name of a public GPG cert and be returned by gpg --list-public-keys

# Where should the encrypted files be placed locally.
# This folder should have enough space to store the complete backup job output
# and ideally not be the same storage as the backup job output is located on.
gpgOutputDirectory = "/mnt/pve/nas02backup/encryptedTemp/"
threads = 2  # Number of concurrent threads working on encryption and upload. 1 is recommended if your output directory isn't super quick.

rcloneRemoteName = "gdriveremote:"  # If root of the remote is given, it should end with :
rcloneVerifyUploads = True  # If True, after the upload the local and remote files will have their hashes compared
rcloneRemoveSourceFile = True  # If True, the upload source file will be deleted after upload. Note this is the .enc file and not the original backup files.
rcloneRemoveOldBackups = False # If True, old remote files will be deleted
rcloneRemoveThreshold = "14d" # Backups older than this threshold are deleted. Format: ms|s|m|h|d|w|M|y. Example: 14d = 14 days
