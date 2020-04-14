# Proxmox Encrypted Remote Backup

## What is it?
Proxmox Encrypted Remote Backup (PERB) is a vzdump hook script written in Python. Once the Backup job has finished successfully the script gathers the backed up files (.vma and .log) and puts them in encrypted tar files and then uploads it to an rclone remote destination (currently Google Drive is tested and supported).

## Design choices & Why?

 1. I wanted an excuse to learn python3.
 2. Although I don't have a reason not to, I didn't want to trust rclones encryption, instead PERB uses gpg which is well established and trusted. PERB is small enough that you can validate the code your self and make sure I´m not getting up to any funny business. 
 3. I wanted as little information leak as possible to the cloud storage provider, this solution only makes the numeric VM-id (not VM-name) and the backup timestamp available to the provider.
 4. I was uncomfortable streaming incomplete files to remote destinations, these files might need cluster level access which can be unreliable on remote destinations. Because of this encryption is done locally and then uploaded to the remote. 
 5. G Suite currently offers potentially unlimited storage, making it a great remote backup
 6. PERB is written to log a lot, most of this can be seen directly in the Proxmox GUI when you look at the backup task, even more in $logFile.
 7. If PERB runs in to trouble, in most cases it will exit with an error that will be clearly visible in the Proxmox task list.


## How?
The script is executed by a Proxmox backup job several times (phases) during the backup job, at every execution it´s given information about the backup job which is collected in a job file.

Below several $variables are mentioned, these are found in ProxmoxEncryptedBackupSettings.py
Encryption is done with default gpg ciphers which on my machine is AES256. 
The encryption/upload can be done multi-threaded by setting $threads, but it´s not recommended as in most cases the speed of $gpgOutputDirectory will be your bottle neck.

### Phases
There are four main phases in a Proxmox backup:
1. job-start, this is the first phase. The job performs all the backup phases
2. backup-start, backup-stop, these phases are triggered once for every VM backup.
3. job-end, the job has ended successfully, all VM backups are done, now the magic happens.

### Flow of events
Below is a flow of events, it doesn't cover absolutely everything but the resulting logs ($logFile) do if you are interested. 

1. The phase "job-start" is reached and the hook script is run for the first time, a job file is created in the $jobFolder. The job file is a json file that will contain metadata about the backup jobs execution.
2. backup-start, backup-stop, a VM is backed up, metadata such as paths to the backup files are put in the job file.
3. job-end phase, all the VM backups are complete, the job file is parsed to retrieve all the backed up files (.vma and .log)
4. For every pair of .vma and .log file tar is used to create an uncompressed archive which is piped to gpg.
5. gpg encrypts the file using a certificate you have previously setup and places them in $gpgOutputDirectory as .enc files. 
6. The encrypted files are uploaded to the cloud using a preconfigured rclone remote. If $rcloneVerifyUploads is set to True the hash of the local and remote file will be compared. If $rcloneRemoveSourceFile is set to True the local .enc file will be removed (.vma and .log are not deleted)
7. job files older than $keepJobsForDays are removed.

Steps 4-6 are done in a single thread per VM backup, how many of these threads that are executed at once is determined by $threads

### Decryption
Decryption presumes that you have private key for the gpg recipient on you machine and gpg knows about it. To decrypt simply run:

```
gpg -d your_archive.enc | tar xz
```

## Installation

### Prerequisite:  
 * rclone setup with a remote 
	 *  Tested with v1.45 and google drive 
 * gpg setup with at least a public key for a recipient 
 *  tar 
 *  python3 
	 * The pexpect library needs to be available
		 * python3 -m pip install pexpect
 * ProxmoxEncryptedBackup.py is made executable 
	 * chmod o+x ProxmoxEncryptedBackup.py

### Setup
* Create a folder to keep the python files: /opt/scripting/encryptedRemoteBackup/
* Put the files there:
	* GpgEncrypt.py
	* ProxmoxEncryptedBackup.py
	* ProxmoxEncryptedBackupSettings.py
	* ProxmoxEventHandler.py
	* Rclone.py
* Make ProxmoxEncryptedBackup.py  executable 
	 * chmod o+x ProxmoxEncryptedBackup.py
 * Update ProxmoxEncryptedBackupSettings.py
	 * Se example file for sample settings and documentation
 * Edit /etc/pve/vzdump.cron
	 * Add to relevant jobs: --script /opt/scripting/encryptedRemoteBackup/ProxmoxEncryptedBackup.py 
 * Run the backup job and check the task output and log file



## Gotchas & Troubleshooting

 - G Suite only allows for about 750GB upload per day
 - PERB is only tested with G Suite, but should function with most rclone remotes, however if they dont support MD5 hashing PERB will need to be updated to handle that.
 - $gpgOutputDirectory should if possible not be set to the same storage as the Proxmox backup as this will severley slowdown encryption. PERB will be reading and writing to the same storage. 
 - Check the logs at $logFile and the Proxmox Tasks in the web gui.





