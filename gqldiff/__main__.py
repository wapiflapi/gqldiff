# coding: utf-8

import logging
import json
import sys

import click
import crayons

import graphql

from graphql.utils.introspection_query import introspection_query

from gqldiff.clickgql import SchemaSourceType


logger = logging.getLogger(__name__)


def get_json_schema(schema):
    return graphql.graphql(schema, introspection_query).data['__schema']


def flatten_schema(schema):

    flatschema = {}

    def flatten(data, prefix):

        if isinstance(data, list) and all(
                isinstance(item, dict) and item for item in data
        ):
            for item in data:
                flatten(item, '%s.%s' % (prefix, item['name']))
        elif isinstance(data, dict) and any(
                isinstance(item, list) for item in data.values()
        ):
            for key, value in data.items():
                flatten(value, '%s.%s' % (prefix, key))
        else:
            flatschema[prefix] = data

    flatten(get_json_schema(schema), '')
    return flatschema


def get_additions(flatnew, flatold, filter, symbol='+'):
    return {
        k: {symbol: v} for k, v in flatnew.items()
        if k not in flatold and filter(v)
    }


def get_changes(flatnew, flatold, filter, symbolnew='+', symbolold='-'):

    common = {
        k: (flatnew[k], flatold[k])
        for k in flatnew if k in flatold
    }

    return {
        k: {symbolnew: v1, symbolold: v2}
        for k, (v1, v2) in common.items()
        if v1 != v2 and filter(v1) and filter(v2)
    }


@click.command()
@click.argument('schema-new', type=SchemaSourceType(authenvvar='GQL_AUTH_NEW'))
@click.argument('schema-old', type=SchemaSourceType(authenvvar='GQL_AUTH_OLD'))
@click.option('--additions/--no-additions', 'showadditions', default=False)
@click.option('--deletions/--no-deletions', 'showdeletions', default=True)
@click.option('--changes/--no-changes', 'showchanges', default=True)
@click.option('--minor/--no-minor', 'includeminor', default=False,
              help="Include 'minor' changes, eg: text.")
@click.option('--fail/--no-fail', 'exitwithfail', default=True,
              help="Exit with an error if changes were detected.")
def main(schema_old, schema_new,
         showadditions, showdeletions, showchanges,
         includeminor, exitwithfail):

    flatold = flatten_schema(schema_old)
    flatnew = flatten_schema(schema_new)

    if includeminor:
        def minorfilter(x):
            return True
    else:
        def minorfilter(x):
            return not isinstance(x, str) or x.isupper()

    diff = {}

    if showadditions:
        diff['additions'] = get_additions(
            flatnew, flatold, filter=minorfilter, symbol='+')
    if showdeletions:
        diff['deletions'] = get_additions(
            flatold, flatnew, filter=minorfilter, symbol='-')
    if showchanges:
        diff['changes'] = get_changes(
            flatnew, flatold, filter=minorfilter)

    meta = {
        'additions': ('+', crayons.green),
        'deletions': ('-', crayons.red),
        'changes': ('=', crayons.yellow),
    }

    for sectionname, sectiondata in sorted(diff.items()):
        sectionsymbol, sectioncolor = meta[sectionname]

        print((" %s " % sectionname).upper().center(80, "="))
        print()

        for itemname, itemdata in sorted(sectiondata.items()):

            bold = any(isinstance(val, dict) for val in itemdata.values())
            print(sectioncolor("%s %s" % (sectionsymbol, itemname), bold=bold))

            itemreps = {
                symbol: json.dumps(val, sort_keys=True, indent=4).splitlines()
                for symbol, val in itemdata.items()
            }

            for symbol, rep in sorted(itemreps.items()):
                for line in rep:
                    bold = any(line not in xrep for xrep in itemreps.values())
                    print(crayons.white("%s %s" % (symbol, line), bold=bold))

            print()
        print()

    if exitwithfail and diff:
        sys.exit(1)


main()
