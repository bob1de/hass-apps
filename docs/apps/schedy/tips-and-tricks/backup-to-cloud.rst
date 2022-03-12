Schedy is very usefull if you want to automate actions less frequent as once a week. This example decribes how you can backup your hassio to the cloud using existing hass.io addons
This example uses the example backup hassio to Google drive. See https://github.com/samccauley/addon-hassiogooglebackup#readme how to install.

Since we only use schedy for tasks not already present in Homeassistant the main work is done with a script. This script creates a new snapshot of the current configuration and runs teh backup to Google drive add_on. The only thing schedy has to do is to start the script at the right moment.
my backup script looks like this:

::

backup_conf:
  alias: 'Backup Configuration'
  sequence:
  # Create a new snapshot first
    - service: hassio.snapshot_full
      data_template:
        name: Automated Backup {{ now().strftime('%Y-%m-%d') }}  # Start creating a snapshot
    - delay:
        minutes: 5 # Give system 5 minutes to create the snapshot
    - service: rest_command.google_backup # move the file to Google Drive with the activated account for this homeassistant installation
    
To trigger this script I use schedy with the actor_type: switch. It looks like this

::

schedy_backup:
  module: hass_apps_loader
  class: SchedyApp
  actor_type: switch

  rooms:
    # Room for the houskeeping task which runs 2 times per month
    housekeeping:
      friendly_name: House Keeping

      schedule:
      - value: 'on'
        days: "1, 15" # Each first and 15th day in the month
        start: "03:00:00"
        end: "03:10:00"  #Give the task 10 minutes to finish
        name: Backup Configuration
      - value: 'off'    # off at all other moments

      actors:
        # Script which does configuration snapshot and stores at Google   
        script.backup_conf:



