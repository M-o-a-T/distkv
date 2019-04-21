import pytest
import trio
import mock
from time import time

from trio_click.testing import CliRunner
from .mock_serf import stdtest
from .run import run
from distkv.client import ServerError
from distkv.util import PathLongener

import logging
logger = logging.getLogger(__name__)

async def collect(i,path=()):
    res = []
    pl = PathLongener(path)
    async for r in i:
        r.pop('tock',0)
        r.pop('seq',0)
        pl(r)
        res.append(r)
    return res

@pytest.mark.trio
async def test_41_ssl_basic(autojump_clock):
    async with stdtest(ssl=True, args={'init':123}) as st:
        s, = st.s
        async with st.client() as c:
            assert (await c.request("get_value", path=())).value == 123

            r = await c.request("set_value", path=("foo",), value="hello", nchain=3)
            r = await c.request("set_value", path=("foo","bar"), value="baz", nchain=3)
            r = await c.request("get_value", path=())
            assert r.value == 123

            r = await c.request("get_value", path=("foo",))
            assert r.value == "hello"

            exp = [
                {'path': (), 'value': 123},
                {'path': ('foo',), 'value': 'hello'},
                {'path': ('foo','bar'), 'value': 'baz'},
            ]
            res=[]
            async with c.stream("get_tree", path=(), maxdepth=2) as rr:
                r = await collect(rr)
            assert r == exp

            exp.pop()
            async with c.stream("get_tree", path=(), iter=True, maxdepth=1) as rr:
                r = await collect(rr)
            assert r == exp

            exp.pop()
            async with c.stream("get_tree", path=(), iter=True, maxdepth=0) as rr:
                r = await collect(rr)
            assert r == exp

            r = await c.request("get_value", path=("foo","bar"))
            assert r.value == "baz"

            r = await c.request("get_state", nodes=True, known=True, missing=True, remote_missing=True)
            del r['tock']
            del r['seq']
            assert r == {'nodes': {'test_0': 3}, 'known': {'test_0': ((1, 4),)}, 'missing': {}, 'remote_missing': {}}

            assert (await c.request("get_value", node="test_0", tick=1)).value == 123
            assert (await c.request("get_value", node="test_0", tick=2)).value == "hello"
            assert (await c.request("get_value", node="test_0", tick=3)).value == "baz"

            r = await c.request("set_value", path=(), value=1234, nchain=3)
            assert r.prev==123
            assert r.chain.tick == 4

            # does not yet exist
            with pytest.raises(ServerError):
                await c.request("get_value", node="test_0", tick=8)
            # has been superseded
            with pytest.raises(ServerError):
                await c.request("get_value", node="test_0", tick=1)
            # works
            assert (await c.request("get_value", node="test_0", tick=4)).value == 1234

            r = await c.request("get_state", nodes=True, known=True, missing=True, remote_missing=True)
            del r['tock']
            del r['seq']
            assert r == {'nodes': {'test_0': 4}, 'known': {'test_0': ((1, 5),)}, 'missing': {}, 'remote_missing': {}}
            pass # client end
        pass # server end
