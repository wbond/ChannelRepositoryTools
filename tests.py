import unittest
import imp
import os
import sys
import threading

try:
    from StringIO import StringIO
    import Queue as queue
except (ImportError):
    from io import StringIO
    import queue

import sublime
import sublime_plugin



class StringQueue(queue.Queue):
    def write(self, data):
        self.put(data)

    def flush(self):
        pass


class ChannelRepositoryToolsInsertCommand(sublime_plugin.TextCommand):
    def run(self, edit, string=''):
        self.view.insert(edit, self.view.size(), string)
        self.view.show(self.view.size(), True)


class TestDefaultChannelCommand(sublime_plugin.WindowCommand):

    def run(self, include_repositories=False):
        tests_module, panel, output_queue, on_done = create_resources(self.window)
        if tests_module is None:
            return

        self.window.run_command('show_panel', {'panel': 'output.channel_repository_tools'})
        threading.Thread(target=display_results, args=('Default Channel', panel, output_queue)).start()
        threading.Thread(target=run_standard_tests, args=(tests_module, include_repositories, output_queue, on_done)).start()


class TestRemoteRepositoryCommand(sublime_plugin.WindowCommand):

    def run(self):
        tests_module, panel, output_queue, on_done = create_resources(self.window)
        if tests_module is None:
            return

        def handle_input(url):
            self.window.run_command('show_panel', {'panel': 'output.channel_repository_tools'})
            threading.Thread(target=display_results, args=('Remote Repository', panel, output_queue)).start()
            threading.Thread(target=run_url_tests, args=(tests_module, url, output_queue, on_done)).start()

        self.window.show_input_panel('Repository URL', 'https://example.com/packages.json', handle_input, None, None)


class TestLocalRepositoryCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        tests_module, panel, output_queue, on_done = create_resources(self.view.window())
        if tests_module is None:
            return

        path = self.view.file_name()

        self.view.window().run_command('show_panel', {'panel': 'output.channel_repository_tools'})
        threading.Thread(target=display_results, args=('Local Repository', panel, output_queue)).start()
        threading.Thread(target=run_local_tests, args=(tests_module, path, output_queue, on_done)).start()


def create_resources(window):
    """
    Creates resources necessary to run the tests for a channel or repository

    :param window:
        A instance of a sublime.Window

    :return:
        A tuple containing (test_module, output_panel, output_queue,
        on_done_callback).

        - test_module: package_control_channel/tests/test.py
        - output_panel: a sublime.View
        - output_queue: a thread-safe file-like object
        - on_done_callback: a callback to cleanup resources when complete
    """

    folder = find_channel_folder(window)

    if folder is None:
        sublime.error_message(u'ChannelRepositoryTools\n\nPlease open the ' +
            u'package_control_channel folder. It can be obtained by forking ' +
            u'and then cloning your fork of ' +
            u'https://github.com/wbond/package_control_channel.')
        return (None, None, None, None)

    output_queue = StringQueue()
    panel = window.get_output_panel('channel_repository_tools')
    panel.settings().set('word_wrap', True)

    if sys.version_info >= (3,):
        old_path = os.getcwd()
    else:
        old_path = os.getcwdu()

    os.chdir(folder)
    def on_done():
        output_queue.write("\x04")
        os.chdir(old_path)

    parent_module_info = imp.find_module('tests', ["."])
    imp.load_module('package_control_channel.tests', *parent_module_info)
    module_info = imp.find_module('test', ["./tests"])
    tests = imp.load_module('package_control_channel.tests.test', *module_info)

    return (tests, panel, output_queue, on_done)


def find_channel_folder(window):
    """
    Looks in the window to find the package_control_channel folder.

    :param window:
        A sublime.Window

    :return:
        A folder path, or None if not found
    """

    for folder in window.folders():
        for file_name in ['channel.json', 'repository.json', 'tests/test.py']:
            if not os.path.exists(os.path.join(folder, file_name)):
                break
        # This is only run if all files were found
        else:
            return folder

    return None


def run_local_tests(tests, path, output_queue, on_done):
    """
    Runs tests for a repository on the local filesystem

    :param tests:
        The tests_module from create_resources()

    :param path:
        The local filesystem path to the repository

    :param output_queue:
        The file-like object to write output to

    :param on_done:
        A callback to execute when the tests are complete
    """

    class RepositoryTests(tests.TestContainer, unittest.TestCase):
        @classmethod
        def generate_repository_tests(cls, stream):
            cls._write(stream, 'Loading ')
            for test in cls._include_tests(path, stream):
                yield test
            cls._write(stream, '\n')

    tests.generate_test_methods(RepositoryTests, output_queue)

    suite = unittest.TestLoader().loadTestsFromTestCase(RepositoryTests)
    result = unittest.TextTestRunner(stream=output_queue, verbosity=1).run(suite)
    on_done()


def run_url_tests(tests, url, output_queue, on_done):
    """
    Runs tests for a repository served via a URL

    :param tests:
        The tests_module from create_resources()

    :param url:
        The URL of the repository

    :param output_queue:
        The file-like object to write output to

    :param on_done:
        A callback to execute when the tests are complete
    """

    class RepositoryTests(tests.TestContainer, unittest.TestCase):
        @classmethod
        def generate_repository_tests(cls, stream):
            cls._write(stream, 'Downloading ')
            for test in cls._include_tests(url, stream):
                yield test
            cls._write(stream, '\n')

    tests.generate_test_methods(RepositoryTests, output_queue)

    suite = unittest.TestLoader().loadTestsFromTestCase(RepositoryTests)
    result = unittest.TextTestRunner(stream=output_queue, verbosity=1).run(suite)
    on_done()


def run_standard_tests(tests, include_repositories, output_queue, on_done):
    """
    Runs the standard tests for the default channel and default repository.

    :param tests:
        The tests_module from create_resources()

    :param include_repositories:
        If all of the remote repositories in the channel should be tested also

    :param output_queue:
        The file-like object to write output to

    :param on_done:
        A callback to execute when the tests are complete
    """

    if include_repositories:
        tests.userargs = ['--test-repositories']
    tests.generate_default_test_methods(output_queue)

    suite = unittest.TestLoader().loadTestsFromModule(tests)
    result = unittest.TextTestRunner(stream=output_queue, verbosity=1).run(suite)
    on_done()


def display_results(headline, panel, string_queue):
    """
    Displays the results of a test run.

    :param headline:
        A title to display in the output panel

    :param panel:
        A sublime.View to write the results to

    :param string_queue:
        The thread-safe queue of output from the test runner
    """

    # We use a function here so that chars is not redefined in the while
    # loop before the timeout get fired
    def write_to_panel(chars):
        sublime.set_timeout(lambda: panel.run_command('channel_repository_tools_insert', {'string': chars}), 10)

    write_to_panel(u'Running %s Tests\n\n  ' % headline)

    while True:
        try:
            chars = string_queue.get(True, 0.1)
            if chars == "\x04":
                break
            write_to_panel(chars.replace('\n', '\n  '))
        except (queue.Empty):
            pass
