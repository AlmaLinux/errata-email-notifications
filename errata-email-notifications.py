# -*- coding: utf-8 -*-
import argparse
import json
import logging
import os
import smtplib
import ssl
import sys

from datetime import datetime
from email.message import EmailMessage
from string import Template
from urllib import request

# For simplicity, we store files in the same folder as the script lives in.
# These files are:
#  * [distribution]_last_processed_ts: One file per distribution
#  * app-passwd: GMail application password
# For this reason, we'll use BASEPATH anytime we read/write files and
# can be changed in the future if needed
BASEPATH = os.path.dirname(__file__)

DISTRIBUTIONS_ERRATA_URL = {
    'almalinux-8': 'https://errata.almalinux.org/8/errata.json',
    'almalinux-9': 'https://errata.almalinux.org/9/errata.json'
}

EMAIL_FROM_NAME = 'AlmaLinux Errata Notifications'
# We create the templates for both subject and content beforehand
SUBJECT_TEMPLATE = Template('[$errata_type Advisory] $errata_title')
# TODO: Read content template from file?
CONTENT_TEMPLATE = Template(
"""Hi, you are receiving an AlmaLinux $errata_type update email because you subscribed to receive errata notifications from AlmaLinux.

Type: $errata_type
Severity: $errata_severity
Release date: $errata_date

Summary:

$errata_description

Full details, updated packages, references, and other related information: $errata_link

This message is automatically generated, please don’t reply. For further questions, please, contact us via the AlmaLinux community chat: https://chat.almalinux.org/.
Want to change your notification settings? Sign in and manage mailing lists on https://lists.almalinux.org.

Kind regards,
AlmaLinux team
""")

def parse_args():
    parser = argparse.ArgumentParser(
        'errata-email-notifications.py',
        description='AlmaLinux errata email notifications script. Parses public errata files '
                    'and sends email notifications to the recipient provided.'
    )
    parser.add_argument(
        '-d', '--distribution', type=str, nargs='+', required=True,
        help='Distribution(s) to fetch/send errata notifications'
    )
    # TODO: Add email verification such as format or even
    # check that it is a valid email address. py3-validate-email
    # python package can help here.
    parser.add_argument(
        '-s', '--sender', type=str, required=True,
        help='Email address to use to send the emails'
    )
    parser.add_argument(
        '-r', '--recipient', type=str, required=True,
        help='Email address to send the emails to'
    )
    parser.add_argument(
        '-v', '--verbose', required=False, action='store_true',
        help='Whether we want to produce verbose logging'
    )

    return parser.parse_args()


class SMTPSession:
    def __init__(self, user):
        self.__user = user
        self.__passwd = self.__read_app_passwd()
        self.__service = smtplib.SMTP_SSL('smtp.gmail.com', 465,
                                          context=ssl.create_default_context())
        # TODO: Add some error handling
        self.__service.login(self.__user, self.__passwd)

    def __read_app_passwd(self):
        try:
            with open(os.path.join(BASEPATH, 'app-passwd'), 'r') as f:
                return f.readline()
        except FileNotFoundError as err:
            logging.error('Stopped execution of %s, error was: %s', __file__, err)
            sys.exit('Could not read app-passwd file. Please check that you '\
                     'provide an app-passwd file within the scripts folder')


    def send(self, msg):
        logging.debug('SMTPSession::send_email: %s', msg.as_string())
        self.__service.send_message(msg)


    def close(self):
        self.__service.quit()


class ErrataEmailNotifications:
    def __init__(self, distributions, sender, recipient):
        self.distributions = distributions
        self.sender = sender
        self.recipient = recipient
        self.smtp_session = SMTPSession(sender)


    def run(self):
        for dist in self.distributions:
            # Check that the user doesn't enter an invalid distributon
            if (dist not in DISTRIBUTIONS_ERRATA_URL):
                logging.warning('Skipping %s as it is not a valid distribution', dist)
                continue

            logging.debug('Processing erratas for distribution %s', dist)
            errata_json_url = DISTRIBUTIONS_ERRATA_URL[dist]
            errata_data = self.fetch_errata_data(errata_json_url)
            if not errata_data:
                logging.warning('Could not fetch errata file for %s, skipping', dist)
                continue

            # Check last processed and succesfully sent errata email
            last_processed_ts_file = dist + '_last_processed_ts'
            if not os.path.exists(last_processed_ts_file):
                # This is the first time the script is running.
                # To avoid sending an email for every errata entry,
                # we'll create the file with the last updated errata entry.
                # Next time the script runs is going to only send emails
                # with the most recent errata entries.
                self.save_last_processed_ts(last_processed_ts_file,
                                       errata_data[0]['updated_date']['$date'])
                logging.warning('Skipping notifications for %s as it looks like ' \
                                'is the first time this script is running', dist)
                continue

            with open(os.path.join(BASEPATH, last_processed_ts_file), 'r') as f:
                last_processed_ts = f.readline()
            # Only take those whose ts is bigger than last_processed_ts
            new_erratas = [
                x for x in errata_data
                if x['updated_date']['$date'] > int(last_processed_ts)
            ]
            logging.debug('Found %d new erratas for %s distribution',
                len(new_erratas), dist
            )

            # We want to start sending notifications from the oldest one
            for errata in reversed(new_erratas):
                # TODO: Make an errata class so retrieving info in the way
                # we need is more comfortable for our purposes
                email_subject = SUBJECT_TEMPLATE.substitute(
                    errata_type=errata['type'].capitalize(),
                    # TODO: Add some checks to ensure that we include
                    # the errata_id at the beginning of the title.
                    # Apparently, there's no strict format, we just copy
                    # the errata info from RHEL and sometimes it differs
                    errata_title=errata['title']
                )
                email_body = CONTENT_TEMPLATE.substitute(
                    errata_type=errata['type'].capitalize(),
                    errata_severity=errata['severity'].capitalize(),
                    errata_date=self.ts_to_date(errata['updated_date']['$date']),
                    errata_description=errata['description'],
                    errata_link=self.get_almalinux_errata_href(errata)
                )

                msg = EmailMessage()
                msg['From'] = f'{EMAIL_FROM_NAME} <{self.sender}>'
                msg['To'] = self.recipient
                msg['Subject'] = email_subject
                msg.set_content(email_body)

                try:
                    self.smtp_session.send(msg)
                    self.save_last_processed_ts(last_processed_ts_file,
                                                errata['updated_date']['$date'])
                except:
                    logging.error('Could not send errata notification email')

        self.smtp_session.close()


    def fetch_errata_data(self, url):
        logging.debug('Fetching errata data from %s', url)
        # TODO: If this script requires a considerable allocation of memory, we can
        # figure out if we can publish the errata json files sorted by date.
        # This way we can think about reading the response in chunks and stop reading
        # when we reach the last_processed_ts. This could save some memory allocation
        # during the execution of the script.
        try:
            response = request.urlopen(url)
            data = json.loads(response.read())
            # We want to return sorted erratas in descending order
            sorted_data = sorted(data,
                                 key=lambda x: x['updated_date']['$date'],
                                 reverse=True)
        except:
            # Maybe more fine grained exception handling?
            sorted_data = None
        finally:
            return sorted_data


    def save_last_processed_ts(self, file_to_write, ts):
        with open(os.path.join(BASEPATH, file_to_write), 'w') as f:
            f.write(str(ts))
        logging.info('Updated %s with timestamp %s', file_to_write, ts)


    def ts_to_date(self, ts):
        # We get ts in milliseconds
        return datetime.utcfromtimestamp(ts/1000).strftime('%Y-%m-%d')


    def get_almalinux_errata_href(self, errata):
        href = ''
        for ref in errata['references']:
            # TODO: Better check if type equals to 'self'?
            if ref['id'] == errata['updateinfo_id']:
                href = ref['href']
                break
        return href


if __name__ == '__main__':
    args = parse_args()

    # Set debug level
    # TODO: Maybe allowing specific logging level?
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=log_level)

    errata_notifications = ErrataEmailNotifications(
            args.distribution,
            args.sender,
            args.recipient)

    errata_notifications.run()
