# -*- coding: utf-8 -*-

import re
import json
import sys
from operator import itemgetter

if sys.version_info >= (3,):
    from urllib.request import urlopen
    from collections import OrderedDict
else:
    from urllib2 import urlopen
    from ordereddict import OrderedDict

import sublime
import sublime_plugin


class UpgradeRepositorySchemaCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        whole_file = sublime.Region(0, self.view.size())
        text = self.view.substr(whole_file)
        result, output, extra = self.upgrade_repository(text)

        if result == 'error':
            sublime.error_message(u'ChannelRepositoryTester\n\n' + output)
        elif result == 'message':
            sublime.message_dialog(u'ChannelRepositoryTester\n\n' + output)
        else:
            self.view.replace(edit, whole_file, output)
            if extra:
                sublime.message_dialog(u'ChannelRepositoryTester\n\n' + extra)

    def upgrade_repository(self, json_string):
        """
        Takes an old repository JSON string and converts it to version 2.0.

        :param json_string:
            The JSON string to convert

        :return:
            A tuple of (result, output, extra). The result may be 'error',
            'message' or 'success'. If 'error' or 'message', the output is the
            message. If the result is 'success', output is the new JSON. The extra
            value is a string containing extra information about the output.
        """

        try:
            repo = json.loads(json_string)
        except (Exception) as e:
            return ('error', u'The contents of the current view does not appear ' +
                u'to be valid JSON.', None)

        if 'schema_version' not in repo:
            return ('error', u'The JSON does not have a "schema_version" key, ' +
                u'and thus does not appear to be a repository file.', None)

        if repo['schema_version'] == '3.0.0':
            return ('message', u'The JSON indicates it is using schema 3.0.0, ' +
                u'thus it does not need to be upgraded.', None)

        if 'packages' not in repo:
            return ('error', u'The JSON does not have a "packages" key, and ' +
                u'thus does not appear to be a repository file.', None)

        output = OrderedDict()
        output['schema_version'] = '3.0.0'
        output['packages'] = []

        has_download_specifics = False
        create_tags = []

        for package in repo['packages']:
            new_package = OrderedDict()

            if repo['schema_version'] != '2.0':
                new_package['name'] = package.get('name', '')

                old_author = package.get('author', 'Unknown')
                if old_author == "Your name or github username":
                    old_author = 'Unknown'
                old_homepage = package.get('homepage', '')
                github_match = re.match('https?://github.com/([^/]+)/([^/]+)$', old_homepage, re.I)
                bitbucket_match = re.match('https?://bitbucket.org/([^/]+)/([^/]+)$', old_homepage, re.I)

                if github_match or bitbucket_match:
                    github_author_mismatch = github_match and github_match.group(1) != old_author
                    bitbucket_author_mismatch = bitbucket_match and bitbucket_match.group(1) != old_author
                    if (github_author_mismatch or bitbucket_author_mismatch) and old_author != 'Unknown':
                        new_package['author'] = old_author

                    new_package['details'] = old_homepage

                else:
                    new_package['description'] = package.get('description', '')
                    new_package['author'] = old_author
                    new_package['homepage'] = old_homepage

                new_package['releases'] = []

                last_modified = package.get('last_modified', '2011-09-01 00:00:00')
                for platform in package.get('platforms', {}):
                    old_releases = package['platforms'][platform]
                    for old_release in old_releases:
                        release = OrderedDict()

                        if platform != '*':
                            release['platforms'] = platform

                        release['sublime_text'] = '<3000'

                        old_url = old_release.get('url', '')
                        old_url = old_url.replace('://nodeload.github.com/', '://codeload.github.com/')
                        old_url = re.sub('^(https://codeload.github.com/[^/]+/[^/]+/)zipball(/.*)$', '\\1zip\\2', old_url)
                        old_version = old_release.get('version', '1.0.0')

                        # For some reason at least one user had an extra /tree segment in their URL
                        github_tag_match = re.match('https://codeload.github.com/([^/]+/[^/]+)(/tree)?/zip/v?' + re.escape(old_version) + '$', old_url)
                        # Alternate forms of the zip download URLs for GitHub
                        if not github_tag_match:
                            github_tag_match = re.match('https://github.com/([^/]+/[^/]+)/archive/v?' + re.escape(old_version) + '.zip$', old_url)
                        if not github_tag_match:
                            github_tag_match = re.match('https://github.com/([^/]+/[^/]+)/zipball/v?' + re.escape(old_version), old_url)

                        github_different_tag_match = re.match('https://codeload.github.com/([^/]+/[^/]+)/zip/v?[\d\._]+$', old_url)
                        if not github_different_tag_match:
                            github_different_tag_match = re.match('https://github.com/([^/]+/[^/]+)/archive/v?[\d\._]+\.zip$', old_url)
                        if not github_different_tag_match:
                            github_different_tag_match = re.match('https://github.com/([^/]+/[^/]+)/zipball/v?[\d\._]+$', old_url)

                        bitbucket_tag_match = re.match('https://bitbucket.org/([^/]+/[^/]+)/get/v?' + re.escape(old_version) + '\.zip$', old_url)

                        github_master_match = re.match('https://codeload.github.com/([^/]+/[^/]+)/zip/master$', old_url)
                        bitbucket_master_match = re.match('https://bitbucket.org/([^/]+/[^/]+)/get/(master|default)\.zip$', old_url)

                        fixed_version = None
                        if re.match('\d+\.\d+$', old_version):
                            fixed_version = old_version + '.0'
                        else:
                            fixed_version = old_version
                        semver_match = re.match('\d+\.\d+\.\d+$', fixed_version)

                        base = None
                        if semver_match and github_tag_match:
                            base = 'https://github.com/' + github_tag_match.group(1)
                            release['tags'] = True
                            if fixed_version != old_version:
                                release_instructions = 'Create tag %s at https://github.com/%s/releases/new' % (fixed_version, github_tag_match.group(1))
                                if release_instructions not in create_tags:
                                    create_tags.append(release_instructions)

                        elif semver_match and github_different_tag_match:
                            base = 'https://github.com/' + github_different_tag_match.group(1)
                            release['tags'] = True
                            release_instructions = 'Create tag %s at https://github.com/%s/releases/new' % (fixed_version, github_different_tag_match.group(1))
                            if release_instructions not in create_tags:
                                create_tags.append(release_instructions)

                        elif semver_match and bitbucket_tag_match:
                            base = 'https://bitbucket.org/' + bitbucket_tag_match.group(1)
                            release['tags'] = True

                        elif github_master_match:
                            name_repo = github_master_match.group(1)
                            base = 'https://github.com/' + name_repo
                            release['tags'] = True
                            release_instructions = 'Create tag %s at https://github.com/%s/releases/new' % (fixed_version, name_repo)
                            if release_instructions not in create_tags:
                                create_tags.append(release_instructions)

                        elif bitbucket_master_match:
                            base = 'https://bitbucket.org/' + bitbucket_master_match.group(1)
                            release['tags'] = True
                            create_tags.append('Create tag %s and push to BitBucket' % fixed_version)

                        else:
                            has_download_specifics = True
                            release['version'] = old_version
                            release['url'] = old_url
                            release['date'] = last_modified

                        if base and 'details' in new_package and base != new_package['details']:
                            release['base'] = base

                        new_package['releases'].append(release)
            else:
                for key in ['name', 'details', 'description', 'homepage', 'author', 'readme', 'issues', 'donate', 'buy', 'labels', 'previous_names']:
                    if key in package:
                        value = package[key]
                        if key == 'details':
                            value = value.rstrip('/')
                        if 'details' in new_package:

                            # Skip the homepage if it is the same URL as 'details'
                            if key == 'homepage' and value == new_package['details']:
                                continue

                            # Skip default issues values
                            if key == 'issues' and value == new_package['details'] + '/issues':
                                continue

                            # Cleanup variations on readme detection
                            if key == 'readme':
                                details_match = re.match('https://github.com/([^/]+/[^/]+)$', new_package['details'], re.I)
                                if details_match:
                                    readme_regex = re.compile(re.escape(new_package['details']) + '/blob/master/readme(\.(md|mkd|mdown|markdown|textile|creole|rst))?$', re.I)
                                    if re.match(readme_regex, value):
                                        continue
                                    # https://raw.githubusercontent.com/Varriount/NimLime/master/readme.md
                                    readme_regex_2 = re.compile('https://raw.githubusercontent.com/' + re.escape(details_match.group(1)) + '/master/readme(\.(md|mkd|mdown|markdown|textile|creole|rst))?$', re.I)
                                    if re.match(readme_regex_2, value):
                                        continue
                                elif re.match('https://bitbucket.org/[^/]+/[^/]+$', new_package['details'], re.I):
                                    readme_regex = re.compile(re.escape(new_package['details']) + '/(raw|src)/master/readme(\.(md|mkd|mdown|markdown|textile|creole|rst))?$', re.I)
                                    if re.match(readme_regex, value):
                                        continue

                            # Clean up old gittip.com URLs since it is now gratipay.com
                            if key == 'donate':
                                details_match = re.match('https://github.com/([^/]+)/[^/]+$', new_package['details'], re.I)
                                if details_match:
                                    username = details_match.group(1)
                                    gittip_url = 'https://www.gittip.com/%s/' % username
                                    if value == gittip_url:
                                        continue

                        new_package[key] = value

                new_package['releases'] = []
                for old_release in package.get('releases', {}):
                    release = OrderedDict()

                    for key in ['sublime_text', 'platforms']:
                        if key in old_release:
                            release[key] = old_release[key]

                    if 'details' in old_release:
                        details = old_release['details']

                        github_base_match = re.match('https://github.com/([^/]+/[^/]+)$', details)
                        bitbucket_base_match = re.match('https://bitbucket.org/([^/]+/[^/#]+)$', details)

                        github_branch_match = re.match('https://github.com/([^/]+/[^/]+)/tree/(.+)$', details)
                        bitbucket_branch_match = re.match('https://bitbucket.org/([^/]+/[^/]+)/src/(.+)$', details)

                        github_tags_match = re.match('https://github.com/([^/]+/[^/]+)/tags$', details)
                        bitbucket_tags_match = re.match('https://bitbucket.org/([^/]+/[^/#]+)#tags$', details)

                        # We assign values to these vars so we can adds them
                        # in order to the OrderedDict later
                        base = None
                        branch = None
                        tags = None
                        if github_base_match:
                            base = 'https://github.com/' + github_base_match.group(1)
                            branch = 'master'

                        elif bitbucket_base_match:
                            base = 'https://bitbucket.org/' + bitbucket_base_match.group(1)
                            # This is not deterministic, but the default channel
                            # didn't have an example of a base BitBucket URL anyway
                            branch = 'default'

                        elif github_branch_match:
                            base = 'https://github.com/' + github_branch_match.group(1)
                            branch = github_branch_match.group(2)

                        elif bitbucket_branch_match:
                            base = 'https://bitbucket.org/' + bitbucket_branch_match.group(1)
                            branch = bitbucket_branch_match.group(2)

                        elif github_tags_match:
                            base = 'https://github.com/' + github_tags_match.group(1)
                            tags = True

                        elif bitbucket_tags_match:
                            base = 'https://bitbucket.org/' + bitbucket_tags_match.group(1)
                            tags = True

                        if base and 'details' in new_package and base != new_package['details']:
                            release['base'] = base
                        if branch:
                            release['branch'] = branch
                        if tags:
                            release['tags'] = tags

                    for key in ['version', 'url', 'date']:
                        if key in old_release:
                            release[key] = old_release[key]

                    new_package['releases'].append(release)

                # Fill in master branch release for packages that ommited it
                if 'releases' not in package:
                    new_release = OrderedDict()
                    new_release['sublime_text'] = '<3000'
                    new_release['branch'] = 'master'
                    new_package['releases'].append(new_release)

            # Look through for releases that are the same other than the platform.
            # This is usually for packages that work on Linux and OS X.
            merged_releases = {}
            unmerged_releases = []
            for release in new_package['releases']:
                if 'platforms' not in release:
                    unmerged_releases.append(release)
                    continue

                platform = release['platforms']
                sublime_text = release.get('sublime_text', '<3000')

                if 'tags' in release:
                    key = 'tags'
                    if 'base' in release:
                        key += '|%s' % release['base']
                    key += '|%s' % sublime_text
                elif 'branch' in release:
                    key = 'branch|%s' % release['branch']
                    if 'base' in release:
                        key += '|%s' % release['base']
                    key += '|%s' % sublime_text
                else:
                    key = "%s|%s|%s|%s" % (release['version'], release['url'], release['date'], sublime_text)

                if key not in merged_releases:
                    merged_releases[key] = []
                merged_releases[key].append(platform)

            if len(merged_releases) + len(unmerged_releases) != len(new_package['releases']):
                all_versions = True
                new_package['releases'] = unmerged_releases
                for key in merged_releases:
                    new_release = OrderedDict()

                    new_release['platforms'] = sorted(merged_releases[key])
                    # Only used temporarily for sorting releases
                    new_release['platforms-sort'] = ','.join(new_release['platforms'])

                    if len(new_release['platforms']) == 1:
                        new_release['platforms'] = new_release['platforms'][0]

                    key_parts = key.split('|')

                    new_release['sublime_text'] = key_parts[-1]

                    if key_parts[0] == 'tags':
                        new_release['tags'] = True
                        if len(key_parts) == 3:
                            new_release['base'] = key_parts[1]
                        all_versions = False
                    if key_parts[0] == 'branch':
                        new_release['branch'] = key_parts[1]
                        if len(key_parts) == 4:
                            new_release['base'] = key_parts[2]
                        all_versions = False
                    else:
                        version = key_parts[0]
                        url = key_parts[1]
                        date = key_parts[2]
                        new_release['version'] = version
                        new_release['url'] = url
                        new_release['date'] = date

                    new_package['releases'].append(new_release)

                if all_versions:
                    new_package['releases'] = sorted(new_package['releases'], key=itemgetter('platforms-sort'))
                    new_package['releases'] = sorted(new_package['releases'], key=itemgetter('version'), reverse=True)

                for release in new_package['releases']:
                    del release['platforms-sort']

            sublime_text_fixes = {
                # Consistency
                '>2999':  '>=3000',
                '<=2999': '<3000',
                # Semantic mistakes
                '>3000':  '>=3000',
                '<=3000': '<3000'
            }

            # Clean up uncessaru platforms key
            for release in new_package['releases']:
                if 'platforms' not in release:
                    continue

                platforms = release['platforms']
                if isinstance(platforms, list) and len(platforms) == 1:
                    platforms = platforms[0]

                # Remove the platforms key if all platforms are supported
                if platforms == '*':
                    del release['platforms']
                elif 'linux' in platforms and 'windows' in platforms and 'osx' in platforms:
                    del release['platforms']
                # Convert single-item lists to a bare value
                elif isinstance(release['platforms'], list) and not isinstance(platforms, list):
                    release['platforms'] = platforms

                if 'sublime_text' in release:
                    if release['sublime_text'] in sublime_text_fixes:
                        release['sublime_text'] = sublime_text_fixes[release['sublime_text']]

            # We now support an array for the author key
            if 'author' in new_package and new_package['author'].find(',') != -1:
                new_package['author'] = re.split('\s*,\s*', new_package['author'])

            output['packages'].append(new_package)

        extra = None
        if create_tags:
            a = 'a ' if len(create_tags) == 1 else ''
            plural = 's' if len(create_tags) > 1 else ''
            extra = (u'This packages.json has been updated to ' + \
                u'utilize features from schema_version 3.0.0 of Package Control ' + \
                u'so any tags that are in the format MAJOR.MINOR.PATCH will ' + \
                u'automatically be added as a release.\n\n' + \
                u'Please perform the following operations to create ' + \
                u'%stag%s for your release%s so that this new repository ' + \
                u'JSON will properly expose your package downloads:\n\n%s' + \
                u'\n\n' + \
                u'To make future releases, simply create a new tag in your ' + \
                u'repository in the format MAJOR.MINOR.PATCH. You will no ' + \
                u'longer need to update this packages.json file.\n\n' + \
                u'Since you no longer need to manually update this ' + \
                u'packages.json file, the best place for package information ' + \
                u'moving forward is the default Package Control repository ' + \
                u'that is part of the default channel.\n\n' + \
                u'Please consider adding the package information to the ' + \
                u'appropriate JSON file in the ./repository/ folder of the ' + \
                u'default channel and removing your repository URL from the ' + \
                u'channel.json.') % (
                a, plural, plural, '\n'.join(create_tags)
                )

        elif not has_download_specifics and repo['schema_version'] != '2.0':
            extra = u'We‘ve detected that your package is currently using tags ' + \
                u'for releases, great!\n\n' + \
                u'This packages.json has been updated to ' + \
                u'utilize features from schema_version 3.0.0 of Package Control ' + \
                u'so any tags that are in the format MAJOR.MINOR.PATCH will ' + \
                u'automatically be added as a release.\n\n' + \
                u'To make future releases, simply create a new tag in your ' + \
                u'repository in the format MAJOR.MINOR.PATCH. You will no ' + \
                u'longer need to update this packages.json file.\n\n' + \
                u'Since you no longer need to manually update this ' + \
                u'packages.json file, the best place for package information ' + \
                u'moving forward is the default Package Control repository ' + \
                u'that is part of the default channel.\n\n' + \
                u'Please consider adding the package information to the ' + \
                u'appropriate JSON file in the ./repository/ folder of the ' + \
                u'default channel and removing your repository URL from the ' + \
                u'channel.json.'

        json_output = json.dumps(output, indent="\t", ensure_ascii=False)

        # Get rid of multi-line json arrays
        def fold_multiline_array(matches, output):
            for match in matches:
                fixed_match = re.sub('\\[\\s*\n\\s*"', '["', match)
                fixed_match = re.sub('"\\s*\n\s*\\]', '"]', fixed_match)
                fixed_match = re.sub('",\\s*\n\\s*"', '", "', fixed_match)
                output = output.replace(match, fixed_match)
            return output

        author_matches = re.findall('"author": \[.*?\]', json_output, re.S)
        json_output = fold_multiline_array(author_matches, json_output)

        platforms_matches = re.findall('"platforms": \[.*?\]', json_output, re.S)
        json_output = fold_multiline_array(platforms_matches, json_output)

        labels_matches = re.findall('"labels": \[.*?\]', json_output, re.S)
        json_output = fold_multiline_array(labels_matches, json_output)

        previous_names_matches = re.findall('"previous_names": \[.*?\]', json_output, re.S)
        json_output = fold_multiline_array(previous_names_matches, json_output)

        # Trim trailing whitespace
        trailing_regex = re.compile('\s+$', re.M)
        json_output = re.sub(trailing_regex, '', json_output)

        return ('success', json_output + '\n', extra)
