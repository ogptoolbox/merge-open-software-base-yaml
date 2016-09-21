#! /usr/bin/env python3


# merge-open-software-base-yaml -- Merge YAML files describing software
# By: Emmanuel Raviart <emmanuel.raviart@data.gouv.fr>
#
# Copyright (C) 2015, 2016 Etalab
# https://git.framasoft.org/codegouv/merge-open-software-base-yaml
#
# merge-open-software-base-yaml is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# merge-open-software-base-yaml is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http:>www.gnu.org/licenses/>.


"""Harvest CSV files from Google spreadsheet of OGP Toolbox and generate cards."""


import argparse
import codecs
import collections
import csv
import itertools
import json
import logging
import os
import sys
import urllib.request

import requests
from slugify import slugify


# Converters


def to_boolean(values):
    value = to_string(values)
    if value is None:
        return None
    if slugify(value).startswith(('t', 'y')):
        return True
    return False


def to_date(values):
    value = to_string(values)
    if value is None:
        return None
    # TODO
    return value


def to_integer(values):
    value = to_string(values)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def to_string(values):
    if not values:
        return None
    return values[0]


def to_string_list(values):
    return values or None


#


app_name = os.path.splitext(os.path.basename(__file__))[0]
csv_url_template = 'https://docs.google.com/spreadsheets/d/{id}/export?format=csv&id={id}&gid={gid}'
label_translations_by_sheet_name = {
    "Organization": {
        "Name": ("name", to_string),
        "Description-EN": ("description_en", to_string),
        "Type": ("type", to_string),
        "Location": ("location", to_string),
        "URL": ("website", to_string),
        "Email": ("contactEmail", to_string),
        "Uses": ("usesPrograms", to_string_list),
        "Wikipedia EN": ("wikipedia_en", to_string),
        },
    "Platform": {
        "Name": ("name", to_string),
        "Description-EN": ("description_en", to_string),
        "Tag": ("tags", to_string_list),
        "Provider": ("providers", to_string_list),
        "Uses": ("uses", to_string_list),
        "userType": ("userTypes", to_string_list),
        "Start": ("start", to_date),
        "Official website": ("website", to_string),
        "EmailContact": ("contactEmail", to_string),
        "Demo": ("demo", to_string),
        "Logo": ("logo", to_string),
        "Screenshot": ("screenshots", to_string_list),
        "Language": ("languages", to_string_list),
        "Client": ("clients", to_string_list),
        "twitter": ("twitter", to_string),
        "facebook": ("facebook", to_string),
        "forum": ("forum", to_string),
        "TOS": ("tos", to_string),
        "Privacy policy": ("privacyPolicy", to_string),
        "wikipedia-EN": ("wikipedia_en", to_string),
        "wikidata": ("wikidata", to_string_list),
        },
    "Software": {
        "Name": ("name", to_string),
        "Description-EN": ("description_en", to_string),
        "Tag": ("tags", to_string_list),
        "Developer": ("developers", to_string_list),
        "Start": ("start", to_date),
        "Website": ("website", to_string),
        "EmailContact": ("contactEmail", to_string),
        "Demo": ("demo", to_string),
        "Logo": ("logo", to_string),
        "Screenshot": ("screenshots", to_string_list),
        "Language": ("languages", to_string_list),
        "opensource": ("openSource", to_boolean),
        "license": ("licenses", to_string_list),
        "SourceCode": ("sourceCode", to_string),
        "RepoStars": ("repoStars", to_integer),
        "bugtracker": ("bugtracker", to_string),
        "version": ("version", to_string),
        "versionDate": ("versionDate", to_date),
        "programmingLanguages": ("programmingLanguages", to_string_list),
        "stackexchangeTag": ("stackexchangeTag", to_string),
        "wikipedia-EN": ("wikipedia_en", to_string),
        "wikidata": ("wikidata", to_string_list),
        "twitter": ("twitter", to_string),
        "facebook": ("facebook", to_string),
        "forum": ("forum", to_string),
        "UsedBy": ("usedBy", to_string_list),
        "InteroperableWith": ("interoperableWith", to_string_list),
        "Client": ("clients", to_string_list),
        },
    "Usage": {
        "Name": ("name", to_string),
        "Description-EN": ("description_en", to_string),
        "Tag": ("tags", to_string_list),
        "Uses": ("usesPrograms", to_string_list),
        "By": ("by", to_string_list),
        "Partner": ("partners", to_string_list),
        "location": ("location", to_string),
        "scale": ("scale", to_string),
        "start": ("start", to_date),
        "stop": ("stop", to_date),
        "UserType": ("userTypes", to_string_list),
        "UserSize": ("userSize", to_string),
        "URL": ("website", to_string),
        "additionalURL": ("additionalUrls", to_string_list),
        "Repo": ("repo", to_string),
        "ContactEmail": ("contactEmail", to_string),
        "Twitter": ("twitter", to_string),
        "Facebook": ("facebook", to_string),
        "Wikipedia (EN)": ("wikipedia_en", to_string),
        },
    }
log = logging.getLogger(app_name)
spreadsheet_id = '1Sjp9PG75Ap-5YBvOWZ-cCUGkNhN41LZlz3OL-gJ-tKU'
sheet_id_by_name = {
    "Software": '1702131855',
    "Platform": '2066765238',
    "Usage": '1374288343',
    "Organization": '475734092',
    }
url_path_by_sheet_name = {
    "Organization": '/organizations',
    "Platform": '/platforms',
    "Software": '/programs',
    "Usage": '/usages',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('server_url', help='URL of OGPToolbox Editor')
    parser.add_argument('-p', '--password', help='password of user')
    parser.add_argument('-u', '--user', help='username or email address of user')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='increase output verbosity')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    # Login to retrieve user API key.
    response = requests.post(urllib.parse.urljoin(args.server_url, 'login'), json = {
        "userName": args.user,
        "password": args.password,
        })
    data = response.json() 
    api_key = data['data']['apiKey']

    response = requests.get(
        urllib.parse.urljoin(args.server_url, '/tags'),
        headers = {
            "OGPToolbox-API-Key": api_key,
            },
        )
    existing_tags = set(
        tool['name']
        for tool in response.json()['data']
        )

    for sheet_name, sheet_id in sheet_id_by_name.items():
        url_path = url_path_by_sheet_name[sheet_name]

        response = requests.get(
            urllib.parse.urljoin(args.server_url, url_path),
            headers = {
                "OGPToolbox-API-Key": api_key,
                },
            )
        existing_entry_by_name = {
            entry['name']: entry
            for entry in response.json()['data']
            }

        response = urllib.request.urlopen(csv_url_template.format(
            gid = sheet_id,
            id = spreadsheet_id,
            ))
        csv_reader = csv.reader(codecs.iterdecode(response, 'utf-8'))
        labels = [
            label.strip()
            for label in next(csv_reader)
            ]
        name_index = labels.index("Name")
        assert name_index >= 0, (sheet_name, labels)
        label_translations = label_translations_by_sheet_name[sheet_name]
        for label in labels:
            editor_label, converter = label_translations.get(label, (None, None))
            if converter is None:
                log.info("Ignoring column {} - {}".format(sheet_name, label))

        for row in csv_reader:
            if all(not cell.strip() for cell in row):
                continue
            name = row[name_index].strip()
            assert name, (sheet_name, labels, name_index, row)
            entry = collections.OrderedDict()
            for label, value in zip(labels, row):
                if slugify(label) == 'delete':
                    continue
                value = value.strip()
                if value and not value.startswith('-'):
                    values = entry.setdefault(label, [])
                    if value not in values:
                        values.append(value)

            editor_entry = collections.OrderedDict()
            for label, values in entry.items():
                editor_label, converter = label_translations.get(label, (None, None))
                if converter is None:
                    continue
                editor_value = converter(values)
                if editor_value is not None:
                    editor_entry[editor_label] = editor_value
            for tag in editor_entry.get('tags', []):
                if tag not in existing_tags:
                    log.info('New tag: {}'.format(tag))
                    response = requests.post(
                        urllib.parse.urljoin(args.server_url, '/tags'),
                        headers = {
                            "OGPToolbox-API-Key": api_key,
                            },
                        json = dict(name = tag),
                        )
                    existing_tags.add(tag)

            existing_entry = existing_entry_by_name.get(name)
            if existing_entry is None:
                log.info('New {}: {}'.format(sheet_name, name))
                response = requests.post(
                    urllib.parse.urljoin(args.server_url, url_path),
                    headers = {
                        "OGPToolbox-API-Key": api_key,
                        },
                    json = editor_entry,
                    )
            else:
                updated_entry = existing_entry.copy()
                changed = False
                for key, value in editor_entry.items():
                    if key not in updated_entry:
                        updated_entry[key] = value
                        changed = True
                if changed:
                    log.info('Update {}: {}'.format(sheet_name, name))
                    response = requests.put(
                        urllib.parse.urljoin(args.server_url, '{}/{}'.format(url_path, updated_entry['id'])),
                        headers = {
                            "OGPToolbox-API-Key": api_key,
                            },
                        json = updated_entry,
                        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
