import re
import json
import sys
from collections import OrderedDict
from operator import itemgetter

if sys.version_info >= (3,):
    from urllib.request import urlopen
else:
    from urllib2 import urlopen

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

        if repo['schema_version'] == '2.0':
            return ('message', u'The JSON indicates it is using schema 2.0, ' +
                u'thus it does not need to be upgraded.', None)

        if 'packages' not in repo:
            return ('error', u'The JSON does not have a "packages" key, and ' +
                u'thus does not appear to be a repository file.', None)

        output = OrderedDict()
        output['schema_version'] = '2.0'
        output['packages'] = []

        has_download_specifics = False
        create_tags = []

        for package in repo['packages']:
            new_package = OrderedDict()
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

            last_modified = package.get('last_modified', '2011-09-01 00:00:00')
            new_package['releases'] = []

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

                    if semver_match and github_tag_match:
                        release['details'] = 'https://github.com/' + github_tag_match.group(1) + '/tags'
                        if fixed_version != old_version:
                            release_instructions = 'Create tag %s at https://github.com/%s/releases/new' % (fixed_version, github_tag_match.group(1))
                            if release_instructions not in create_tags:
                                create_tags.append(release_instructions)

                    elif semver_match and github_different_tag_match:
                        release['details'] = 'https://github.com/' + github_different_tag_match.group(1) + '/tags'
                        release_instructions = 'Create tag %s at https://github.com/%s/releases/new' % (fixed_version, github_different_tag_match.group(1))
                        if release_instructions not in create_tags:
                            create_tags.append(release_instructions)

                    elif semver_match and bitbucket_tag_match:
                        release['details'] = 'https://bitbucket.org/' + bitbucket_tag_match.group(1) + '#tags'

                    elif github_master_match:
                        name_repo = github_master_match.group(1)
                        release['details'] = 'https://github.com/' + name_repo + '/tags'
                        release_instructions = 'Create tag %s at https://github.com/%s/releases/new' % (fixed_version, name_repo)
                        if release_instructions not in create_tags:
                            create_tags.append(release_instructions)

                    elif bitbucket_master_match:
                        release['details'] = 'https://bitbucket.org/' + bitbucket_master_match.group(1) + '#tags'
                        create_tags.append('Create tag %s and push to BitBucket' % fixed_version)

                    else:
                        has_download_specifics = True
                        release['version'] = old_version
                        release['url'] = old_url
                        release['date'] = last_modified

                    new_package['releases'].append(release)

            # Look through for releases that are the same other than the platform.
            # This is usually for packages that work on Linux and OS X.
            merged_releases = {}
            unmerged_releases = []
            for release in new_package['releases']:
                if 'platforms' not in release:
                    unmerged_releases.append(release)
                    continue

                platform = release['platforms']

                if 'details' in release:
                    key = release['details']
                else:
                    key = "%s|%s|%s" % (release['version'], release['url'], release['date'])

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

                    new_release['sublime_text'] = '<3000'

                    if key.find('|') == -1:
                        new_release['details'] = key
                        all_versions = False
                    else:
                        version, url, date = key.split('|')
                        new_release['version'] = version
                        new_release['url'] = url
                        new_release['date'] = date

                    new_package['releases'].append(new_release)

                if all_versions:
                    new_package['releases'] = sorted(new_package['releases'], key=itemgetter('platforms-sort'))
                    new_package['releases'] = sorted(new_package['releases'], key=itemgetter('version'), reverse=True)

                for release in new_package['releases']:
                    del release['platforms-sort']

            output['packages'].append(new_package)

        extra = None
        if create_tags:
            a = 'a ' if len(create_tags) == 1 else ''
            plural = 's' if len(create_tags) > 1 else ''
            extra = (u'This packages.json has been updated to ' + \
                u'utilize features from schema_version 2.0 of Package Control ' + \
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

        elif not has_download_specifics:
            extra = u'We‘ve detected that your package is currently using tags ' + \
                u'for releases, great!\n\n' + \
                u'This packages.json has been updated to ' + \
                u'utilize features from schema_version 2.0 of Package Control ' + \
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

        # Get rid of multi-line platforms keys. This is a total hack, but the
        # python json module doesn't offer a way to override the serialization
        # of specific elements.
        json_output = re.sub('"platforms": \[\s+"linux",\s+"osx"\s+\]', '"platforms": ["linux", "osx"]', json_output)
        json_output = re.sub('"platforms": \[\s+"linux",\s+"windows"\s+\]', '"platforms": ["linux", "windows"]', json_output)
        json_output = re.sub('"platforms": \[\s+"osx",\s+"windows"\s+\]', '"platforms": ["osx", "windows"]', json_output)

        return ('success', json_output, extra)
