# -*- coding: utf-8 -*-
"""Heroku API helper functions.

Heroku module uses the Envoy library to run the Heroku
Toolbelt CLI commands.

It also includes the HerokuRelease class, which encapsulates
the information returned from the API about a specific
application release.

"""
from dateutil import parser
import click
import envoy
import requests

from heroku_tools.settings import SETTINGS

HEROKU_API_URL_STEM = 'https://api.heroku.com/apps/%s/'
HEROKU_API_URL_RELEASES = HEROKU_API_URL_STEM + 'releases'
HEROKU_API_URL_CONFIG_VARS = HEROKU_API_URL_STEM + 'config-vars'
HEROKU_API_TOKEN = SETTINGS['heroku_api_token']


class HerokuError(Exception):
    """Error raised when something goes wrong interacting with Heroku."""
    pass


class HerokuRelease(object):
    """Encapsulates a release as described by the Heroku release API.

    See https://devcenter.heroku.com/articles/platform-api-reference#release
    """

    def __init__(self, raw):
        """Initialise new object from raw JSON as return from API."""
        self._json = raw

    def __unicode__(self):
        return (
            u"Release %s [%s] of %s, deployed by %s at %s" %
            (
                self.version,
                self.commit,
                self.application,
                self.deployed_by,
                self.deployed_at
            )
        )

    def __str__(self):
        return unicode(self).encode('utf-8')

    @property
    def application(self):
        """The name of the application."""
        return self._json['app']['name']

    @property
    def commit(self):
        """The hash of the commit deployed in the release."""
        if self.description.startswith('Promote'):
            # "Promote my-app v123 75c70c5"
            return self.description.split(' ')[3]
        elif self.description.startswith('Deploy'):
            # "Deploy 75c70c5"
            return self.description.split(' ')[1]
        else:
            return "invalid"

    @property
    def deployed_at(self):
        """The datetime at which the deployment occurred."""
        return parser.parse(self._json['updated_at'])

    @property
    def description(self):
        """The description supplied by Heroku for the release."""
        return str(self._json['description'])

    @property
    def version(self):
        """The version number (supplied by Heroku) of the release."""
        return self._json['version']

    @property
    def deployed_by(self):
        """The name of the person responsible for the release."""
        return str(self._json['user']['email'])

    def get_config_vars(self):
        """Fetch config vars for the app release via API."""
        return call_api(
            HEROKU_API_URL_CONFIG_VARS,
            self.application
        )

    @classmethod
    def get_latest_deployment(cls, application):
        """Return the most recent release as HerokuRelease object.

        See https://devcenter.heroku.com/articles/platform-api-reference#release  # noqa
        """
        releases = call_api(
            HEROKU_API_URL_RELEASES,
            application,
            range_header='version;max=10,order=desc'
        )

        for release in releases:
            description = release.get('description', '').split(' ')[0]
            if description in (u'Promote', u'Deploy'):
                return HerokuRelease(release)
            else:
                click.echo("Ignoring release: %s" % release.get('description'))

        raise HerokuError(u"No deployments found in API response.")


def call_api(endpoint, application, range_header=None):
    """Call Heroku API and return response.json()."""
    url = endpoint % application
    auth = requests.auth.HTTPBasicAuth('', HEROKU_API_TOKEN)
    headers = {'Accept': 'application/vnd.heroku+json; version=3'}
    if range_header is not None:
        headers['Range'] = range_header
    try:
        return requests.get(url, auth=auth, headers=headers).json()
    except Exception as ex:
        raise HerokuError(u"Error calling Heroku API: %s" % ex)


def run_cmd(application, command):
    """Run a Heroku Toolbelt command and return output."""
    cmd = "heroku %s --app %s" % (command, application)
    retval = envoy.run(cmd)
    if retval.status_code > 0:
        raise HerokuError(
            u"Error running Heroku command '%s': %s"
            % (cmd, retval.std_err)
        )
    return retval.std_out


def run_command(application, command):
    """Run a command against a Heroku application."""
    return run_cmd(application, "run %s" % command)


def toggle_maintenance(application, maintenance_on):
    """Toggle the Heroku maintenance feature on/off."""
    on_off = "on" if maintenance_on else "off"
    return run_cmd(application, "maintenance:%s" % on_off)


def promote_app(application):
    """Run the Heroku pipeline promote command."""
    return run_cmd(application, "pipeline:promote")
