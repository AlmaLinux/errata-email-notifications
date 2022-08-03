# AlmaLinux Errata Email Notifications
This script checks the public errata json files for AlmaLinux distributions and sends notification emails with every new update.

## Requirements

### Dependencies

* requests = 2.28.1

We used Python 3.8 when creating the script but should work with any Python 3.x version.

The recommended workflow to install dependencies is:
```
python3 -m venv venv && source venv/bin/activate
pip3 install -r requirements.txt
```

### Gmail Application Password
In order for the script to run, you have to provide a [Gmail Application Password](https://support.google.com/accounts/answer/185833).
This password needs to be put in a file called _app-passwd_, and needs to be placed in the same folder as the script.

There are other options to send emails:
* Using [Google Cloud APIs for GMail](https://developers.google.com/gmail/api)
* Setting up a _Postfix_ instance in the same server where the script is going to run

For now we wanted to keep it simple, we can change the approach if we decide is worth doing it.

## Usage
The script needs to be called with 3 arguments:
* The distribution(s) we want to use to generate the errata notifications. Supported distributions are _almalinux-8_ and _almalinux-9_
* The email we want to use when sending the email notifications. For now it only supports Gmail accounts.
* The email we want to send the notifications to

The script has also optional arguments to:
* Indicate the logfile you want the script to use to log its output. By default the logs will go into _errata-email-notifications.log_
* Indicate whether you want to enable the verbose mode and get the logging output to console. When enabled, the script won't log into a logfile, this is useful when you're working on the script or debugging it.

If you want to send errata notifications for AlmaLinux 8, you can run:
```python errata-email-notifications.py -d almalinux-8 -s sender@gmail.com -r recipient@mail.com```

If you want to send errata notifications for both AlmaLinux 8 and 9, and also enabling the verbose mode, you can run:
```python errata-email-notifications.py -d almalinux-8 almalinux-9 -s sender@gmail.com -r recipient@mail.com -v```

__Note:__ To avoid the unfortunate situation of sending notifications for every errata in a distribution, the first run will only save the last errata's timestamp.
The next run the script will send the email notifications if there are any of them.

## Contributing
Any question? Found a bug? File an [issue](https://github.com/AlmaLinux/errata-email-notifications/issues).
Do you want to contribute with source code?
1. Fork the repository on Github
2. Create a new feature branch
3. Write your change
4. Submit a pull request
