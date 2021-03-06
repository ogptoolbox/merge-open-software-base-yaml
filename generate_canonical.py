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


import argparse
import collections
import functools
import logging
import os
import shutil
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


def extract_from_list(language, value):
    if value is not None:
        for item in value:
            yield language, item


def extract_from_name_id(value):
    if value is not None:
        name = value['name']
        if isinstance(name, str):
            yield 'en', name
        else:
            yield from extract_from_value_by_language(name)


def extract_from_name_id_list(value):
    if value is not None:
        for item in value:
            yield from extract_from_name_id(item)


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


def extract_from_value_by_language(value):
    if value is not None:
        yield from value.items()


def extract_from_wikidata(value):
    if value is not None:
        for item in value:
            yield item.get('xml:lang'), item['value']


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

    assert os.path.exists(args.source_dir)
    if os.path.exists(args.target_dir):
        for filename in os.listdir(args.target_dir):
            if filename.startswith('.'):
                continue
            path = os.path.join(args.target_dir, filename)
            if os.path.isdir(path):
                shutil.rmtree(path)
    else:
        os.makedirs(args.target_dir)

    # ACTORS

    entity_type = 'actors'
    source_entity_type_dir = os.path.join(args.source_dir, entity_type)
    target_entity_type_dir = os.path.join(args.target_dir, entity_type)
    if not os.path.exists(target_entity_type_dir):
        os.makedirs(target_entity_type_dir)
    for yaml_file_path, entry in iter_yaml_files(source_entity_type_dir):
        yaml_file_relative_path = os.path.relpath(yaml_file_path, source_entity_type_dir)

        canonical = collections.OrderedDict()

        # name
        # Lowercase version of this name is the unique name of the actor and the slugified version of this unique name
        # is the file name for the actor.
        for path in (
                'civic-graph.name',
                ):
            value = get_path(entry, path)
            if value is not None:
                value = value.strip()
                if value:
                    canonical['name'] = dict(
                        source = get_path_source(path),
                        value = value,
                        )
                    break

        # longDescription
        # Description of the actor, for each supported language, in a map indexed by the two letter (ISO-639-1)
        # language code
        for language, paths in dict(
                en = (
                    'civic-graph.description',
                    ),
                es = (
                    ),
                fr = (
                    ),
                ).items():
            for path in paths:
                value = get_path(entry, path)
                if value is not None:
                    value = value.strip()
                    if value:
                        canonical.setdefault('longDescription', {})[language] = dict(
                            source = get_path_source(path),
                            value = value,
                            )
                        break

        # tags
        sources_by_value_by_language = {}
        for path, extractor in (
                ('civic-graph.categories', extract_from_name_id_list),
                ('civic-graph.type', functools.partial(extract_from_value, 'en')),
                ):
            source = get_path_source(path)
            value = get_path(entry, path)
            for language, item in extractor(value):
                assert isinstance(item, str), (path, language, item, value)
                if language is not None and item is not None:
                    item = item.strip()
                    if item:
                        sources_by_value_by_language.setdefault(language, {}).setdefault(item, set()).add(source)
        if sources_by_value_by_language:
            for language, sources_by_value in sources_by_value_by_language.items():
                canonical.setdefault('tags', {})[language] = [
                    dict(
                        sources = sorted(sources),
                        value = value,
                        )
                    for value, sources in sorted(sources_by_value.items())
                    ]

        # website
        for path in (
                'civic-graph.url',
                ):
            value = get_path(entry, path)
            if value is not None:
                value = value.strip()
                if value:
                    canonical['website'] = dict(
                        source = get_path_source(path),
                        value = value,
                        )
                    break

        if canonical:
            entry['canonical'] = canonical
        with open(os.path.join(target_entity_type_dir, yaml_file_relative_path), 'w') as yaml_file:
            yaml.dump(entry, yaml_file, allow_unicode=True, default_flow_style=False, indent=2, width=120)

    # PROJECTS

    entity_type = 'projects'
    source_entity_type_dir = os.path.join(args.source_dir, entity_type)
    target_entity_type_dir = os.path.join(args.target_dir, entity_type)
    if not os.path.exists(target_entity_type_dir):
        os.makedirs(target_entity_type_dir)
    for yaml_file_path, entry in iter_yaml_files(source_entity_type_dir):
        yaml_file_relative_path = os.path.relpath(yaml_file_path, source_entity_type_dir)

        canonical = collections.OrderedDict()

        # name
        # Lowercase version of this name is the unique name of the project and the slugified version of this unique name
        # is the file name for the project.
        for path in (
                'participatedb.Name',
                ):
            value = get_path(entry, path)
            if value is not None:
                value = value.strip()
                if value:
                    canonical['name'] = dict(
                        source = get_path_source(path),
                        value = value,
                        )
                    break

        # longDescription
        # Description of the project, for each supported language, in a map indexed by the two letter (ISO-639-1)
        # language code
        for language, paths in dict(
                en = (
                    'participatedb.Description',
                    ),
                es = (
                    ),
                fr = (
                    ),
                ).items():
            for path in paths:
                value = get_path(entry, path)
                if value is not None:
                    value = value.strip()
                    if value:
                        canonical.setdefault('longDescription', {})[language] = dict(
                            source = get_path_source(path),
                            value = value,
                            )
                        break

        # tags
        sources_by_value_by_language = {}
        for path, extractor in (
                ('participatedb.Category', functools.partial(extract_from_singletion_or_list, 'en')),
                ('participatedb.category', functools.partial(extract_from_value, 'en')),
                ):
            source = get_path_source(path)
            value = get_path(entry, path)
            for language, item in extractor(value):
                assert isinstance(item, str), (path, language, item, value)
                if language is not None and item is not None:
                    item = item.strip()
                    if item:
                        sources_by_value_by_language.setdefault(language, {}).setdefault(item, set()).add(source)
        if sources_by_value_by_language:
            for language, sources_by_value in sources_by_value_by_language.items():
                canonical.setdefault('tags', {})[language] = [
                    dict(
                        sources = sorted(sources),
                        value = value,
                        )
                    for value, sources in sorted(sources_by_value.items())
                    ]

        # tools
        sources_by_value = {}
        for path, extractor in (
                ('participatedb.Tools used', functools.partial(extract_from_list, None)),
                ):
            source = get_path_source(path)
            value = get_path(entry, path)
            for language, item in extractor(value):
                assert isinstance(item, str), (path, language, item, value)
                if language in (None, 'en') and item is not None:
                    item = item.strip()
                    if item:
                        sources_by_value.setdefault(item, set()).add(source)
        if sources_by_value:
            canonical['tools'] = [
                dict(
                    sources = sorted(sources),
                    value = value,
                    )
                for value, sources in sorted(sources_by_value.items())
                ]

        # website
        for path in (
                'participatedb.Web',
                ):
            value = get_path(entry, path)
            if value is not None:
                value = value.strip()
                if value:
                    canonical['website'] = dict(
                        source = get_path_source(path),
                        value = value,
                        )
                    break

        if canonical:
            entry['canonical'] = canonical
        with open(os.path.join(target_entity_type_dir, yaml_file_relative_path), 'w') as yaml_file:
            yaml.dump(entry, yaml_file, allow_unicode=True, default_flow_style=False, indent=2, width=120)

    # TOOLS

    entity_type = 'tools'
    source_entity_type_dir = os.path.join(args.source_dir, entity_type)
    target_entity_type_dir = os.path.join(args.target_dir, entity_type)
    if not os.path.exists(target_entity_type_dir):
        os.makedirs(target_entity_type_dir)
    for yaml_file_path, entry in iter_yaml_files(source_entity_type_dir):
        yaml_file_relative_path = os.path.relpath(yaml_file_path, source_entity_type_dir)

        canonical = collections.OrderedDict()

        # bugTracker
        # URL of the service where bugs related to the tool can be reported
        for path in (
                'wikidata.bug_tracking_system.0.value',
                'ogptoolbox-framacalc.URL suivi de bogues',
                ):
            value = get_path(entry, path)
            if value is not None:
                value = value.strip()
                if value:
                    canonical['bugTracker'] = dict(
                        source = get_path_source(path),
                        value = value,
                        )
                    break

        # license
        # Name of the license governing the tool.
        for path in (
                'wikidata.license_label.0.value',
                'civicstack.license.name.en',
                'nuit-debout.Nom de la licence',
                'ogptoolbox-framacalc.Licence',
                ):
            value = get_path(entry, path)
            if value is not None:
                value = value.strip()
                if value:
                    canonical['license'] = dict(
                        source = get_path_source(path),
                        value = value,
                        )
                    break

        # name
        # Lowercase version of this name is the unique name of the tool and the slugified version of this unique name is
        # the file name for the tool.
        for path in (
                'debian_appstream.Name.C',
                'wikidata.label.0.value',
                'civic-tech-field-guide.name',
                'civicstack.name',
                'tech-plateforms.Name',
                'nuit-debout.Outil',
                'participatedb.Name',
                'harnessing-collaborative-technologies.title',
                'ogptoolbox-framacalc.Nom',
                ):
            value = get_path(entry, path)
            if value is not None:
                value = value.strip()
                if value:
                    canonical['name'] = dict(
                        source = get_path_source(path),
                        value = value,
                        )
                    break

        # longDescription
        # Description of the tool, for each supported language, in a map indexed by the two letter (ISO-639-1) language
        # code
        for path, extractor in (
                ('wikidata.description', extract_from_wikidata),
                ('debian.description.en.long_description', functools.partial(extract_from_value, 'en')),
                ('debian.description.es.long_description', functools.partial(extract_from_value, 'es')),
                ('debian.description.fr.long_description', functools.partial(extract_from_value, 'fr')),
                ('civicstack.description', extract_from_value_by_language),
                ('tech-plateforms.About', functools.partial(extract_from_value, 'en')),
                ('participatedb.Description', functools.partial(extract_from_value, 'en')),
                ('harnessing-collaborative-technologies.description', functools.partial(extract_from_value, 'en')),
                ('nuit-debout.Détails', functools.partial(extract_from_value, 'fr')),
                ('ogptoolbox-framacalc.Description', functools.partial(extract_from_value, 'fr')),
                ):
            source = get_path_source(path)
            value = get_path(entry, path)
            for language, item in extractor(value):
                assert isinstance(item, str), (path, language, item, value)
                if language is not None and item is not None:
                    item = item.strip()
                    if item:
                        canonical_value_by_language = canonical.setdefault('longDescription', {})
                        if language not in canonical_value_by_language:
                            canonical_value_by_language[language] = dict(
                                source = source,
                                value = item,
                                )

        # programmingLanguages
        sources_by_value = {}
        for path, extractor in (
                ('civicstack.technology', extract_from_name_id_list),
                ):
            source = get_path_source(path)
            value = get_path(entry, path)
            for language, item in extractor(value):
                assert isinstance(item, str), (path, language, item, value)
                if language in (None, 'en') and item is not None:
                    item = item.strip()
                    if item:
                        sources_by_value.setdefault(item, set()).add(source)
        if sources_by_value:
            canonical['programmingLanguages'] = [
                dict(
                    sources = sorted(sources),
                    value = value,
                    )
                for value, sources in sorted(sources_by_value.items())
                ]

        # screenshot
        # The URL of a screenshot displaying the tool user interface
        for path in (
                'debian.screenshot.large_image_url',
                'wikidata.image.0.value',
                "ogptoolbox-framacalc.Capture d'écran",
                'harnessing-collaborative-technologies.logo_url',
                ):
            value = get_path(entry, path)
            if value is not None:
                value = value.strip()
                if value:
                    canonical['screenshot'] = dict(
                        source = get_path_source(path),
                        value = value,
                        )
                    break

        # sourceCode
        # URL from which the source code of the tool can be obtained.
        for path in (
                'wikidata.source_code_repository.0.value',
                'civicstack.github',
                'nuit-debout.Lien vers le code',
                'ogptoolbox-framacalc.URL code source',
                ):
            value = get_path(entry, path)
            if value is not None:
                value = value.strip()
                if value:
                    canonical['sourceCode'] = dict(
                        source = get_path_source(path),
                        value = value,
                        )
                    break

        # stackexchangeTag:
        # Tag from http://stackexchange.org/ uniquely associated with the tool.
        for path in (
                'wikidata.stack_exchange_tag.0.value',
                'ogptoolbox-framacalc.Tag stack exchange',
                ):
            value = get_path(entry, path)
            if value is not None:
                value = value.strip()
                if value:
                    canonical['stackexchangeTag'] = dict(
                        source = get_path_source(path),
                        value = value,
                        )
                    break

        # tags
        sources_by_value_by_language = {}
        for path, extractor in (
                ('civic-tech-field-guide.category', functools.partial(extract_from_value, 'en')),
                # ('civicstack.category', extract_from_name_id),
                ('civicstack.tags', extract_from_name_id_list),
                ('debian_appstream.Categories', functools.partial(extract_from_list, 'en')),
                ('harnessing-collaborative-technologies.category', functools.partial(extract_from_value, 'en')),
                ('nuit-debout.Fonction', functools.partial(extract_from_value, 'fr')),
                ('ogptoolbox-framacalc.Catégorie', functools.partial(extract_from_value, 'fr')),
                ('participatedb.Category', functools.partial(extract_from_singletion_or_list, 'en')),
                ('participatedb.category', functools.partial(extract_from_value, 'en')),
                ('tech-plateforms.CivicTech or GeneralPurpose', functools.partial(extract_from_value, 'en')),
                ('tech-plateforms.Functions', functools.partial(extract_from_value, 'en')),
                ('tech-plateforms.AppCivist Service 1', functools.partial(extract_from_value, 'en')),
                ('tech-plateforms.AppCivist Service 2', functools.partial(extract_from_value, 'en')),
                ('tech-plateforms.AppCivist Service 3', functools.partial(extract_from_value, 'en')),
                ('wikidata.genre_label', extract_from_wikidata),
                ('wikidata.instance_of_label', extract_from_wikidata),
                ):
            source = get_path_source(path)
            value = get_path(entry, path)
            for language, item in extractor(value):
                assert isinstance(item, str), (path, language, item, value)
                if language is not None and item is not None:
                    item = item.strip()
                    if item:
                        sources_by_value_by_language.setdefault(language, {}).setdefault(item, set()).add(source)
        if sources_by_value_by_language:
            for language, sources_by_value in sources_by_value_by_language.items():
                canonical.setdefault('tags', {})[language] = [
                    dict(
                        sources = sorted(sources),
                        value = value,
                        )
                    for value, sources in sorted(sources_by_value.items())
                    ]

        if canonical:
            entry['canonical'] = canonical
        with open(os.path.join(target_entity_type_dir, yaml_file_relative_path), 'w') as yaml_file:
            yaml.dump(entry, yaml_file, allow_unicode=True, default_flow_style=False, indent=2, width=120)

    return 0


if __name__ == "__main__":
    sys.exit(main())
