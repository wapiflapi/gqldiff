# coding: utf-8

import json
import os

import click
import gql
import graphql
import requests

from gql.transport.requests import RequestsHTTPTransport


try:
    # python2
    from urlparse import urlparse
except ImportError:
    # python3
    from urllib.parse import urlparse


class SchemaSourceType(click.ParamType):
    name = 'schema_source'

    def __init__(self, authenvvar=None, **kwargs):
        self.authenvvar = authenvvar
        return super().__init__(**kwargs)

    def convert_from_url(self, value, param, ctx):

        headers = {}
        if self.authenvvar is not None:
            headers['Authorization'] = os.environ.get(self.authenvvar)

        try:
            client = gql.Client(
                transport=RequestsHTTPTransport(
                    url=value, headers=headers, use_json=True,
                ),
                fetch_schema_from_transport=True,
            )
        except requests.exceptions.HTTPError as e:
            m = str(e)
            if self.authenvvar is not None and e.response.status_code == 401:
                m += ' : Try setting %s in the environment.' % self.authenvvar
            self.fail(m, param=param, ctx=ctx)
        except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.RequestException
        ) as e:
            self.fail(e, param=param, ctx=ctx)

        return client.schema

    def convert_from_file(self, value, param, ctx):
        f = click.File('r').convert(value, param, ctx)

        try:
            introspection = json.load(f)['data']
            schema = graphql.build_client_schema(introspection)
        except (ValueError, KeyError) as e:
            self.fail(
                'File content is not valid a graphql schema %s.' % e,
                param=param, ctx=ctx
            )

        return schema

    def convert(self, value, param, ctx):

        parsedurl = urlparse(value)

        if parsedurl.scheme and parsedurl.netloc:
            schema = self.convert_from_url(value, param, ctx)
        else:
            schema = self.convert_from_file(value, param, ctx)

        return schema


SCHEMA_SOURCE = SchemaSourceType()
