#! /usr/bin/env python3


# merge-open-software-base-yaml -- Merge YAML files describing software
# By: Emmanuel Raviart <emmanuel.raviart@data.gouv.fr>
#
# Copyright (C) 2015, 2016 Etalab
# https::#git.framasoft.org/etalab/merge-open-software-base-yaml
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


import argparse
import collections
import functools
import logging
import os
import sys

import apt_pkg
import yaml, yaml.constructor, yaml.parser, yaml.scanner


# YAML configuration


class folded_str(str):
    pass


class literal_str(str):
    pass


def dict_constructor(loader, node):
    return collections.OrderedDict(loader.construct_pairs(node))


def dict_representer(dumper, data):
    return dumper.represent_dict(sorted(data.items()))


yaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, dict_constructor)

yaml.add_representer(folded_str, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str',
    data, style='>'))
yaml.add_representer(literal_str, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str',
    data, style='|'))
yaml.add_representer(dict, dict_representer)
yaml.add_representer(collections.OrderedDict, dict_representer)
yaml.add_representer(str, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str', data))


#


app_name = os.path.splitext(os.path.basename(__file__))[0]
args = None
log = logging.getLogger(app_name)


def extract_from_civicstack_name_id(value):
    if value is not None:
        name = value['name']
        if isinstance(name, str):
            yield 'en', name
        else:
            yield from name.items()


def extract_from_civicstack_name_id_list(value):
    if value is not None:
        for item in value:
            yield from extract_from_civicstack_name_id(item)


def extract_from_list(language, value):
    if value is not None:
        for item in value:
            yield language, item


def extract_from_singletion_or_list(language, value):
    if value is not None:
        if isinstance(value, list):
            for item in value:
                yield language, item
        else:
            yield language, value


def extract_from_value(language, value):
    if value is not None:
        yield language, value


def get_path(item, path):
    if item is None:
        return item
    if not path:
        return item
    split_path = path.split('.', 1)
    key = split_path[0]
    if key.isdigit():
        if not isinstance(item, (list, tuple)):
            return None
        index = int(key)
        value = item[index] if 0 <= index < len(item) else None
    else:
        if not isinstance(item, dict):
            return None
        value = item.get(key)
    if len(split_path) <= 1:
        return value
    return get_path(value, split_path[1])


def get_path_source(path):
    return path.split('.', 1)[0]


def iter_yaml_files(dir):
    assert os.path.exists(dir), "Directory doesn't exist: {}".format(dir)
    for sub_dir, dirs_name, filenames in os.walk(dir):
        for dir_name in dirs_name[:]:
            if dir_name.startswith('.'):
                dirs_name.remove(dir_name)
        for filename in filenames:
            if not filename.endswith(".yaml"):
                continue
            yaml_file_path = os.path.join(sub_dir, filename)
            with open(yaml_file_path) as yaml_file:
                try:
                    yield yaml_file_path, yaml.load(yaml_file)
                except (UnicodeDecodeError, yaml.constructor.ConstructorError, yaml.parser.ParserError,
                        yaml.scanner.ScannerError):
                    log.warning("Invalid syntax in YAML file {}".format(yaml_file_path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir', help='path of source data directory')
    parser.add_argument('target_dir', help='path of target directory for generated YAML files')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='increase output verbosity')
    global args
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    if not os.path.exists(args.target_dir):
        os.makedirs(args.target_dir)

    for yaml_file_path, entry in iter_yaml_files(args.source_dir):
        assert yaml_file_path.startswith(args.source_dir)
        yaml_file_relative_path = os.path.relpath(yaml_file_path, args.source_dir)

        canonical = collections.OrderedDict()

        # name
        # Lowercase version of this name is the unique name of the tool and the slugified version of this unique name is
        # the file name for the tool.
        for path in (
                'debian_appstream.Name.C',
                'wikidata.program_enlabel.0.value',
                'civicstack.name',
                'tech-plateforms.Name',
                'nuit-debout.Outil',
                'participatedb.Name',
                'ogptoolbox-framacalc.Nom',
                ):
            value = get_path(entry, path)
            if value is not None:
                canonical['name'] = collections.OrderedDict(sorted(dict(
                    source = get_path_source(path),
                    value = value,
                    ).items()))
                break

        # license
        # Name of the license governing the tool.
        for path in (
                'wikidata.license_enlabel.0.value',
                'civicstack.license.name.en',
                'nuit-debout.Nom de la licence',
                'ogptoolbox-framacalc.Licence',
                ):
            value = get_path(entry, path)
            if value is not None:
                canonical['license'] = collections.OrderedDict(sorted(dict(
                    source = get_path_source(path),
                    value = value,
                    ).items()))
                break

        # sourceCode
        # URL from which the source code of the tool can be obtained.
        for path in (
                'wikidata.source_code.0.value',
                'civicstack.github',
                'nuit-debout.Lien vers le code',
                'ogptoolbox-framacalc.URL code source',
                ):
            value = get_path(entry, path)
            if value is not None:
                canonical['sourceCode'] = collections.OrderedDict(sorted(dict(
                    source = get_path_source(path),
                    value = value,
                    ).items()))
                break

        # bugTracker
        # URL of the service where bugs related to the tool can be reported
        for path in (
                'wikidata.bug_tracker.0.value',
                'ogptoolbox-framacalc.URL suivi de bogues',
                ):
            value = get_path(entry, path)
            if value is not None:
                canonical['bugTracker'] = collections.OrderedDict(sorted(dict(
                    source = get_path_source(path),
                    value = value,
                    ).items()))
                break

        # longDescription
        # Description of the tool, for each supported language, in a map indexed by the two letter (ISO-639-1) language
        # code
        for language, paths in dict(
                en = (
                    'debian.description.en.long_description',
                    'civicstack.description.en',
                    'tech-plateforms.About',
                    'participatedb.Description',
                    ),
                es = (
                    'debian.description.es.long_description',
                    'civicstack.description.es',
                    ),
                fr = (
                    'debian.description.fr.long_description',
                    'civicstack.description.fr',
                    'nuit-debout.Détails',
                    'ogptoolbox-framacalc.Description',
                    ),
                ).items():
            for path in paths:
                value = get_path(entry, path)
                if value is not None:
                    canonical.setdefault('longDescription', {})[language] = collections.OrderedDict(sorted(dict(
                        source = get_path_source(path),
                        value = value,
                        ).items()))
                    break

        # screenshot
        # The URL of a screenshot displaying the tool user interface
        for path in (
                'debian.screenshot.large_image_url',
                'wikidata.image.0.value',
                "ogptoolbox-framacalc.Capture d'écran",
                ):
            value = get_path(entry, path)
            if value is not None:
                canonical['screenshot'] = collections.OrderedDict(sorted(dict(
                    source = get_path_source(path),
                    value = value,
                    ).items()))
                break

        # stackexchangeTag:
        # Tag from http://stackexchange.org/ uniquely associated with the tool.
        for path in (
                'wikidata.stackexchange_tag.0.value',
                'ogptoolbox-framacalc.Tag stack exchange',
                ):
            value = get_path(entry, path)
            if value is not None:
                canonical['stackexchangeTag'] = collections.OrderedDict(sorted(dict(
                    source = get_path_source(path),
                    value = value,
                    ).items()))
                break

        # tags
        sources_by_value_by_language = {}
        for path, extractor in (
                ('civicstack.category', extract_from_civicstack_name_id),
                ('civicstack.technology', extract_from_civicstack_name_id_list),
                ('debian_appstream.Categories', functools.partial(extract_from_list, 'en')),
                ('nuit-debout.Fonction', functools.partial(extract_from_value, 'fr')),
                ('ogptoolbox-framacalc.Catégorie', functools.partial(extract_from_value, 'fr')),
                ('ogptoolbox-framacalc.Technologies', functools.partial(extract_from_list, 'fr')),
                ('participatedb.Category', functools.partial(extract_from_singletion_or_list, 'en')),
                ('participatedb.category', functools.partial(extract_from_value, 'en')),
                ('tech-plateforms.CivicTech or GeneralPurpose', functools.partial(extract_from_value, 'en')),
                ):
            source = get_path_source(path)
            value = get_path(entry, path)
            for language, item in extractor(value):
                assert isinstance(item, str), (path, language, item, value)
                if item:
                    sources_by_value_by_language.setdefault(language, {}).setdefault(item, set()).add(source)
        if sources_by_value_by_language:
            for language, sources_by_value in sources_by_value_by_language.items():
                canonical.setdefault('tags', {})[language] = [
                    collections.OrderedDict(sorted(dict(
                        sources = sorted(sources),
                        value = value,
                        ).items()))
                    for value, sources in sorted(sources_by_value.items())
                    ]

        if canonical:
            entry['canonical'] = canonical
        with open(os.path.join(args.target_dir, yaml_file_relative_path), 'w') as yaml_file:
            yaml.dump(entry, yaml_file, allow_unicode=True, default_flow_style=False, indent=2, width=120)

    return 0


if __name__ == "__main__":
    sys.exit(main())
