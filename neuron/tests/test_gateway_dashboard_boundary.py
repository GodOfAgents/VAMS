"""Actual NodeInfo/dashboard AST; HTMLResponse/clock fixtures, no ASGI claim."""
import ast
from dataclasses import asdict,dataclass,field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
import sys
import types
from typing import Dict,List,Optional
import unittest

def _source_and_base():
    # Script mode: SOURCE=server.py BASE=pre-repair copy. Under pytest the
    # real gateway/server.py is tested and the scope comparison is skipped.
    args=sys.argv[1:3]
    if len(args)==2 and Path(args[0]).name=='server.py' and all(Path(a).is_file() for a in args):
        return Path(args[0]),Path(args[1])
    return Path(__file__).resolve().parents[2]/'gateway'/'server.py',None

SOURCE,BASE=_source_and_base();NOW=1700000000.0

class Response:
    def __init__(self,content):self.body=content.encode('utf-8');self.status_code=200

class Tags(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.tags=[];self.text=[]
    def handle_starttag(self,tag,attrs):self.tags.append(tag)
    def handle_data(self,data):self.text.append(data)

def load_actual_parts():
    tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
    selected=[]
    for node in tree.body:
        if isinstance(node,ast.ImportFrom) and node.module=='html':selected.append(node)
        elif isinstance(node,ast.ClassDef) and node.name=='NodeInfo':selected.append(node)
        elif isinstance(node,ast.AsyncFunctionDef) and node.name=='dashboard':
            node.decorator_list=[];selected.append(node)
    module=types.ModuleType('dashboard_actual_source');module.__file__=str(SOURCE)
    module.__dict__.update(dataclass=dataclass,field=field,asdict=asdict,datetime=datetime,
        Dict=Dict,List=List,Optional=Optional,time=types.SimpleNamespace(time=lambda:NOW),
        NODE_TIMEOUT=120,nodes={},HTMLResponse=Response,VERSION='fixture-version')
    sys.modules[module.__name__]=module
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(SOURCE),'exec'),module.__dict__)  # nosec B102 # test-only exec of AST-extracted repository source
    return module

class DashboardBoundaryTests(unittest.TestCase):
    def setUp(self):self.m=load_actual_parts()
    def render(self):
        # The extracted renderer has no await/I/O. Drive its one return without
        # an event loop (Windows loop creation allocates local socket pairs).
        coroutine=self.m.dashboard()
        try:
            try:coroutine.send(None)
            except StopIteration as completed:response=completed.value
            else:self.fail('Renderer yielded outside the supported display boundary')
        finally:coroutine.close()
        self.assertEqual(response.status_code,200)
        return response.body.decode('utf-8')
    def node(self,name='plain-node',online=True,**kw):
        return self.m.NodeInfo(node_id=name,last_seen=NOW if online else NOW-121,
            first_seen=NOW-61,last_block=1234,network='mocha-4',heartbeat_count=2,**kw)
    def test_empty_dashboard_control(self):
        rendered=self.render();self.assertIn('No nodes connected yet',rendered);self.assertEqual(self.m.nodes,{})
    def test_real_online_node_renders_without_missing_attribute(self):
        node=self.node();self.m.nodes[node.node_id]=node
        rendered=self.render();self.assertIn('plain-node',rendered);self.assertIn('1,234',rendered)
        self.assertIn(node.last_seen_formatted,rendered);self.assertEqual(node.heartbeat_count,2)
    def test_real_offline_node_renders_without_missing_attribute(self):
        node=self.node(online=False);self.m.nodes[node.node_id]=node
        self.assertIn('<tr class="offline">',self.render())
    def test_formatter_property_and_dictionary_keep_existing_value(self):
        node=self.node();expected=datetime.fromtimestamp(node.last_seen).strftime('%H:%M:%S')
        self.assertEqual(node.last_seen_formatted,expected)
        self.assertEqual(node.to_dict()['last_seen_formatted'],expected)
        self.assertEqual(node.to_dict()['node_id'],'plain-node')
        self.assertNotIn('last_seen_formatted',asdict(node))
    def test_online_recency_and_offline_order_are_retained(self):
        older=self.node('older');older.last_seen=NOW-10
        newer=self.node('newer');offline=self.node('offline',online=False)
        self.m.nodes.update(older=older,offline=offline,newer=newer)
        rendered=self.render();self.assertLess(rendered.index('newer</td>'),rendered.index('older</td>'))
        self.assertLess(rendered.index('older</td>'),rendered.index('offline</td>'))
    def test_fixture_row_sink_escapes_all_text_in_both_branches(self):
        # Fixture supplies the full row interface to isolate the latent HTML
        # sink from the separate actual-NodeInfo missing-property crash.
        for online in (True,False):
            with self.subTest(online=online):
                self.m.nodes.clear();attack='<img src=x onerror="alert(1)"> & <svg onload=alert(2)>'
                row=types.SimpleNamespace(node_id=attack,is_online=online,last_seen=NOW,last_block=1234,
                    network='<script>network</script>',heartbeat_count=2,uptime='<b>up</b>',
                    last_seen_formatted='<i>time</i>')
                self.m.nodes['fixture']=row
                rendered=self.render();parsed=Tags();parsed.feed(rendered)
                for tag in ('img','svg','script','b','i'):self.assertNotIn(tag,parsed.tags)
                visible=''.join(parsed.text)
                for value in (attack,row.network,row.uptime,row.last_seen_formatted):self.assertIn(value,visible)
    def test_real_node_unicode_and_markup_are_text(self):
        name='Jos\u00e9 <worker> & "quoted"';node=self.node(name);self.m.nodes[name]=node
        parsed=Tags();parsed.feed(self.render());self.assertNotIn('worker',parsed.tags)
        self.assertIn(name,''.join(parsed.text));self.assertEqual(node.node_id,name)
    @unittest.skipUnless(BASE is not None,'change-scope check needs a pre-repair BASE file (script mode)')
    def test_other_authentication_and_handler_ast_are_unchanged(self):
        def unaffected(path):
            tree=ast.parse(path.read_text(encoding='utf-8'));nodes=[]
            for node in tree.body:
                if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in ('NodeInfo','dashboard'):continue
                if isinstance(node,ast.ImportFrom) and node.module=='html':continue
                nodes.append(node)
            return ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False)
        self.assertEqual(unaffected(SOURCE),unaffected(BASE))
        def dashboard_decorators(path):
            node=next(n for n in ast.parse(path.read_text(encoding='utf-8')).body
                      if isinstance(n,ast.AsyncFunctionDef) and n.name=='dashboard')
            return [ast.dump(d,include_attributes=False) for d in node.decorator_list]
        self.assertEqual(dashboard_decorators(SOURCE),dashboard_decorators(BASE))
