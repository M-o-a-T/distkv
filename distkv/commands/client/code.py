# command line interface

import os
import sys
import trio_click as click
from pprint import pprint
import yaml

from distkv.util import (
    attrdict,
    PathLongener,
    MsgReader,
    PathShortener,
    split_one,
    NotGiven,
)
from distkv.client import open_client, StreamedRequest
from distkv.command import Loader
from distkv.default import CFG
from distkv.server import Server
from distkv.auth import loader, gen_auth
from distkv.exceptions import ClientError
from distkv.util import yprint

import logging

logger = logging.getLogger(__name__)


@main.group()
@click.pass_obj
async def cli(obj):
    """Manage code stored in DistKV."""
    pass


@cli.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print the complete result. Default: just the value",
)
@click.option(
    "-s", "--script", type=click.File(mode="w", lazy=True), help="Save the code here"
)
@click.argument("path", nargs=-1)
@click.pass_obj
async def get(obj, path, verbose, script):
    """Read a code entry"""
    if not path:
        raise click.UsageError("You need a non-empty path.")
    res = await obj.client._request(
        action="get_value",
        path=obj.cfg['codes']['prefix'] + path,
        iter=False,
        nchain=3 if verbose else 0,
    )
    if not verbose:
        res = res.value
    if script:
        code = res.pop("code", None)
        if code is not None:
            print(code, file=script)
    yprint(res)


@cli.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print the complete result. Default: just the value",
)
@click.option("-a", "--async", "async_", is_flag=True, help="The code is async")
@click.option("-t", "--thread", is_flag=True, help="The code should run in a worker thread")
@click.option(
    "-s", "--script", type=click.File(mode="r"), help="File with the code"
)
@click.option("-y", "--yaml", "yaml_", is_flag=True, help="load the 'script' file as YAML")
@click.option(
    "-c",
    "--chain",
    type=int,
    default=0,
    help="Length of change list to return. Default: 0",
)
@click.argument("path", nargs=-1)
@click.pass_obj
async def set(obj, path, chain, thread, verbose, script, yaml_, async_):
    """Save Python code."""
    if async_:
        if thread:
            raise click.UsageError("You can't specify both '--async' and '--thread'.")
    else:
        if thread:
            async_ = False
        else:
            async_ = None

    if not path:
        raise click.UsageError("You need a non-empty path.")

    if yaml_:
        msg = yaml.safe_load(script)
    else:
        msg = {}
    if "value" in msg:
        chain = msg.get('chain', chain)
        msg = msg['value']
    if async_ is not None or 'is_async' not in msg:
        msg['is_async'] = async_

    if "code" in msg:
        if script:
            raise click.UsageError("Duplicate script")
    else:
        if not script:
            raise click.UsageError("Missing script")
        msg["code"] = script.read()

    res = await obj.client._request(
        action="set_value",
        value=msg,
        path=obj.cfg['codes']['prefix'] + path,
        iter=False,
        nchain=3 if verbose else 0,
        **({"chain":chain} if chain else {})
    )
    if verbose:
        yprint(res)


@cli.group('module')
@click.pass_obj
async def mod(obj):
    """
    Change the code of a module stored in DistKV
    """

@mod.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print the complete result. Default: just the value",
)
@click.option(
    "-s", "--script", type=click.File(mode="w", lazy=True), help="Save the code here"
)
@click.argument("path", nargs=-1)
@click.pass_obj
async def get(obj, path, verbose, script):
    """Read a module entry"""
    if not path:
        raise click.UsageError("You need a non-empty path.")
    res = await obj.client._request(
        action="get_value",
        path=obj.cfg['modules']['prefix'] + path,
        iter=False,
        nchain=3 if verbose else 0,
    )
    if not verbose:
        res = res.value
    if script:
        code = res.pop("code", None)
        if code is not None:
            print(code, file=script)

    yprint(res)


@mod.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print the complete result. Default: just the value",
)
@click.option(
    "-s", "--script", type=click.File(mode="r"), help="File with the module's code"
)
@click.option("-y", "--yaml", "yaml_", is_flag=True, help="load the 'script' file as YAML")
@click.option(
    "-c",
    "--chain",
    type=int,
    default=0,
    help="Length of change list to return. Default: 0",
)
@click.argument("path", nargs=-1)
@click.pass_obj
async def set(obj, path, chain, verbose, script, yaml_):
    """Save a Python module to DistKV."""
    if not path:
        raise click.UsageError("You need a non-empty path.")

    if yaml_:
        msg = yaml.safe_load(script)
    else:
        msg = {}
    if "value" in msg:
        chain = msg.get('chain', chain)
        msg = msg['value']

    if "code" not in msg:
        if script:
            raise click.UsageError("Duplicate script")
    else:
        if not script:
            raise click.UsageError("Missing script")
        msg["code"] = script.read()

    res = await obj.client._request(
        action="set_value",
        value=msg,
        path=obj.cfg['modules']['prefix'] + path,
        iter=False,
        nchain=3 if verbose else 0,
        **({"chain":chain} if chain else {})
    )
    if verbose:
        yprint(res)
