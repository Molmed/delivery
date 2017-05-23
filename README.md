Simple script, wrapping mover deliveries
========================================

Installation
------------

```
conda create --name=ugc_delivery_script python=2.7
source activate ugc_delivery_script
pip install -r requirements.txt
```

Running
-------

The delivery script is run on a single directory, which should contain all files to be delivered. You also need to specify a staging area, to which the delivery will first be copied before handing it over to Mover. It's also necessary that the email given is the email that the responsible PI has listed in Supr.

Here is an example of how to run the script:

```
# You need to be in the python environment in which you installed the
# script dependencies before you can run it.
source activate ugc_delivery_script
python deliver.py --project dummy --sensitive --path test_delivery/ --staging_area staging_area/ --email 'me@example.com' --supr_url https://disposer.c3se.chalmers.se/supr-test/api --supr_api_user <your api user> --supr_api_key <your api key>
```

Please note that the values here need to be substituted with real values for this to work, and the `supr_url` needs to be pointing to the real supr instance, at https://supr.snic.se/api

The `project` parameter decides that base name for the delivery project in Supr, which will be created on the format `DELIVER_<project_name>_<current date>`
