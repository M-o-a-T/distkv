# command line interface

import os
import sys
import trio_click as click
from pprint import pprint
import json

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

ACL = set("rwdcxena")
# read, write, delete, create, access, enumerate

@main.group()
@click.pass_obj
async def cli(obj):
    """Manage ACLs. Usage: … acl …"""
    pass


@cli.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print the complete result. Default: just the value",
)
@click.pass_obj
async def list(obj, verbose):
    """List ACLs.
    """
    res = await obj.client._request(
        action="enum_internal",
        path=("acl",),
        iter=False,
        nchain=3 if verbose else 0,
    )
    yprint(res)

@cli.command()
@click.option(
    "-d",
    "--as-dict", 
    default=None,
    help="Structure as dictionary. The argument is the key to use "
    "for values. Default: return as list",
)
@click.argument("name", nargs=1)
@click.argument("path", nargs=-1)
@click.pass_obj
async def dump(obj, name, path, as_dict):
    """Dump a complete (or partial) ACL."""
    res = await obj.client._request(
        action="get_tree_internal",
        path=("acl",name)+path,
        iter=True,
    )
    y = {}
    async for r in res:
        if as_dict is not None:
            yy = y
            for p in r.pop("path"):
                yy = yy.setdefault(p, {})
            if "chain" in r:
                yy["chain"] = r.chain
            yy[as_dict] = r.pop("value")
        else:
            y = {}
            y[r.path] = r.value
            yprint([y])

    if as_dict:
        yprint(y)


@cli.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print the complete result. Default: just the value",
)
@click.argument("name", nargs=1)
@click.argument("path", nargs=-1)
@click.pass_obj
async def get(obj, name, path, verbose):
    """Read an ACL.
    
    This command does not test a path. Use "… acl test …" for that.
    """
    if not path:
        raise click.UsageError("You need a non-empty path.")
    res = await obj.client._request(
        action="get_internal",
        path=("acl", name) + path,
        iter=False,
        nchain=3 if verbose else 0,
    )

    if not verbose:
        try:
            res = res.value
        except KeyError:
            if obj.debug:
                print("No value.", file=sys.stderr)
            return
    yprint(res)


@cli.command(name="set")
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print the complete result. Default: just the value",
)
@click.option("-a", "--acl", default="+x", help="The value to set. Start with '+' to add, '-' to remove rights.")
@click.argument("name", nargs=1)
@click.argument("path", nargs=-1)
@click.pass_obj
async def set_(obj, acl, name, path, verbose):
    """Set or change an ACL."""

    if not path:
        raise click.UsageError("You need a non-empty path.")
    if len(acl) == 1 and acl in "+-":
        mode = acl[0]
        acl = acl[1:]
    else:
        mode = "x"
    acl = set(acl)

    if acl - ACL:
        raise click.UsageError("You're trying to set an unknown ACL flag: %r" % (acl-ACL,))

    res = await obj.client._request(
        action="get_internal",
        path=("acl", name) + path,
        iter=False,
        nchain=3 if verbose else 1,
    )
    ov = set(res.get('value', ''))
    if ov - ACL:
        print("Warning: original ACL contains unknown: %r" % (ov-acl,), file=sys.stderr)

    if mode == '-' and not acl:
        res = await obj.client._request(
            action="delete_internal",
            path=("acl", name) + path,
            iter=False,
            chain=res.chain,
        )
        v = "-"

    else:
        if mode == '+':
            v = ov+acl
        elif mode == '-':
            v = ov-acl
        else:
            v = acl
        res = await obj.client._request(
            action="set_internal",
            path=("acl", name) + path,
            value="".join(v),
            iter=False,
            chain=res.get('chain', None),
        )

    if verbose:
        res = {"old": "".join(ov), "new": "".join(v), "chain":res.chain, "tock":res.tock}
        yprint(res)
    else:
        res = {"old": "".join(ov), "new": "".join(v)}
        yprint(res)


@cli.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print the complete result. Default: just the value",
)
@click.option('-m','--mode',default=None, help="Mode letter to test.")
@click.option('-a','--acl',default=None, help="ACL to test. Default: current")
@click.argument("name", nargs=1)
@click.argument("path", nargs=-1)
@click.pass_obj
async def test(obj, name, path, acl, verbose, mode):
    """Test which ACL entry matches a path"""
    if not path:
        raise click.UsageError("You need a non-empty path.")

    if mode is not None and len(mode) != 1:
        raise click.UsageError("Mode must be one letter.")
    res = await obj.client._request(
        action="test_acl",
        path=path,
        iter=False,
        nchain=3 if verbose else 0,
        **({} if mode is None else {'mode': mode}),
        **({} if acl is None else {'acl': acl}),
    )
    if verbose:
        pprint(res)
    elif isinstance(res.access, bool):
        print('+' if res.access else '-')
    else:
        print(res.access)
