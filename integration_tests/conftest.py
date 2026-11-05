import os

import pytest


class EndTestNameLine:
    """
    When run-integration-tests.sh streams the logs of some services (--logs), they are printed while a test runs,
    which would continue the line pytest started with the test's name.
    So that line is ended with "Starting...", and the test's name is printed again with its result.

    This relies on how pytest's verbose terminal reporter writes each test's line:
    it only starts a new line (and writes the test's name) if the current line isn't the test's already.
    """

    def __init__(self, config):
        self.config = config
        self.prefix = (
            None  # The test's name, as pytest writes it at the start of its line
        )

    @property
    def reporter(self):
        return self.config.pluginmanager.get_plugin("terminalreporter")

    @pytest.hookimpl(trylast=True)
    def pytest_runtest_logstart(self):
        # pytest has just written the test's name: end the line
        self.prefix = self.reporter.currentfspath
        self.reporter.write("Starting...", green=True)
        self.reporter.line("")
        # Not writing to a terminal, so the output is buffered: flush it before the logs arrive
        self.reporter.flush()

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        # Write the test's name again, before pytest writes its result, so pytest doesn't add an empty line first
        _, _, word = self.config.hook.pytest_report_teststatus(
            report=report, config=self.config
        )
        if word and self.prefix:
            self.reporter.write(self.prefix)
            self.reporter.currentfspath = self.prefix
            self.prefix = None


def pytest_configure(config):
    if os.environ.get("STREAMING_LOGS"):
        config.pluginmanager.register(EndTestNameLine(config), "end_test_name_line")
