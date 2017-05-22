
import argparse
from datetime import date
from dateutil.relativedelta import relativedelta
import requests
import json
import shutil
import os
import subprocess
import logging
import sys
import time

log = logging.getLogger('deliver')
log.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)


def search_pi_id_by_email(base_url, email, user, key):
    search_person_url = '{}/person/search/'.format(base_url)
    # Search case insensitive
    params = {'email_i': email}
    response = requests.get(search_person_url, params=params, auth=(user, key))

    if response.status_code != 200:
        raise AssertionError("Status code returned when trying to get PI id for email: "
                             "{} was not 200. Response was: {}".format(email, response.content))

    response_as_json = json.loads(response.content)
    matches = response_as_json["matches"]

    if len(matches) < 1:
        raise AssertionError("There were no hits in SUPR for email: {}".format(email))

    if len(matches) > 1:
        raise AssertionError("There we more than one hit in SUPR for email: {}".format(email))

    return matches[0]["id"]


def create_delivery_project(base_url, project_name, pi_id, sensitive_data, user, key):

    supr_date_format = '%Y-%m-%d'

    create_delivery_project_url = '{}/ngi_delivery/project/create/'.format(base_url)

    today = date.today()
    today_formatted = today.strftime(supr_date_format)
    six_months_from_now = today + relativedelta(months=+3)
    six_months_from_now_formatted = six_months_from_now.strftime(supr_date_format)

    payload = {
        'ngi_project_name': project_name,
        'title': "DELIVERY_{}_{}".format(project_name, today_formatted),
        'pi_id': pi_id,
        'start_date': today_formatted,
        'end_date': six_months_from_now_formatted,
        'continuation_name': '',
        # You can use this field to allocate the size of the delivery
        # 'allocated': size_of_delivery,
        # This field can be used to add any data you like
        'api_opaque_data': '',
        'ngi_ready': False,
        'ngi_delivery_status': '',
        'ngi_sensitive_data': sensitive_data
    }

    response = requests.post(create_delivery_project_url,
                             data=json.dumps(payload),
                             auth=(user, key))

    if response.status_code != 200:
        raise AssertionError("Status code returned when trying to create delivery "
                             "project was not 200. Response was: {}".format(response.content))

    return json.loads(response.content)


# -----------------------------------
#         Parse arguments
# -----------------------------------
parser = argparse.ArgumentParser()

parser.add_argument("-p", "--project", help="Name of the project you want to deliver, determines name of "
                                            "delivery project created in Supr", required=True)
parser.add_argument("-i", "--path", help="Path to the directory to deliver", required=True)
parser.add_argument("-s", "--staging_area", help="Path to the directory where directory should"
                                                 " be staged prior to delivery", required=True)
parser.add_argument("-e", "--email", help="Email address to the PI (Must be same as in Supr)", required=True)
parser.add_argument("-u", "--supr_url", help="Base url of Supr instance to use", required=True)
parser.add_argument("-a", "--supr_api_user", help="Supr API user", required=True)
parser.add_argument("-k", "--supr_api_key", help="Supr API key", required=True)
parser.add_argument("-d", "--debug", help="Get debugg level logging information")

# Require an argument specifying whether data is sensitive
sensitive_args = parser.add_mutually_exclusive_group(required=True)
sensitive_args.add_argument("--sensitive", action="store_true", help="Project contains sensitive personal data")
sensitive_args.add_argument("--not-sensitive", action="store_true", help="Project does not contain sensitive "
                                                                         "personal data")

args = parser.parse_args()

# -----------------------------------
#         Input parameters
# -----------------------------------

# Set debug flag
if args.debug:
    log.setLevel(logging.DEBUG)

# The name of the project that you want to deliver
project = args.project

# Path to project to deliver
project_path = args.path

# Path to staging area
staging_area = args.staging_area

# Fetch the emails project pi somehow e.g. from a LIMS/StatusDB/Read from file
pi_email = args.email

# Flag indicating the sensitivity of the data
sensitive_data = args.sensitive

supr_base_url = args.supr_url
supr_api_user = args.supr_api_user
supr_api_key = args.supr_api_key

# -----------------------------------
#         Run delivery
# -----------------------------------

log.info("Starting delivery of project: {}".format(project))

pi_id = search_pi_id_by_email(base_url=supr_base_url,
                              email=pi_email,
                              user=supr_api_user,
                              key=supr_api_key)

log.info("Found a matching PI for email: {}, with id: {}".format(pi_email, pi_id))

# Stage the project into a separate folder (this is really optional if you are ok with not
# being able to access the data after the delivery)
stage_project_path = os.path.join(staging_area, project)

try:
    log.info("Starting to copy {} into {}".format(project_path, stage_project_path))
    shutil.copytree(src=project_path, dst=stage_project_path)
except OSError as e:
    log.error("There already exists a directory at: {} You will need to remove that"
              " before going forward.".format(stage_project_path))
    sys.exit(1)

# Create a delivery project
try:
    delivery_project_info = create_delivery_project(base_url=supr_base_url,
                                                    project_name=project,
                                                    pi_id=pi_id,
                                                    sensitive_data=sensitive_data,
                                                    user=supr_api_user,
                                                    key=supr_api_key)
    supr_name_of_delivery = delivery_project_info['name']
    log.info("Successfully created a delivery project, which got the id: {}".format(supr_name_of_delivery))
except AssertionError as e:
    log.error("Could not create a delivery project. See exception: {}".format(e))
    sys.exit(1)

log.info("Will now sleep for 1 h and 15 min while waiting for Uppmax to sync the projects from Supr...")
time.sleep(60*75)

log.info("Waking up, will now try to start to_outbox")
# Start Mover
try:
    cmd = ['to_outbox', stage_project_path, supr_name_of_delivery]
    output = subprocess.check_output(cmd)
    log.info("Successfully ran mover, here is the mover log: \n {}".format(output))
except subprocess.CalledProcessError as e:
    log.error("Failed to run mover, got exception: {}".format(e))
    sys.exit(1)
