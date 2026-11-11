"""Synthetic delta-transfer tests; no network or real root modifications."""
import base64,json,subprocess,tempfile,unittest
from pathlib import Path
from root190_common import blob,git_tree_entries
from prepare_root190_transfer import compile_plan,standard_tree,encode,RESERVE,BUDGET,CAP
HERE=Path(__file__).resolve().parent
class TransferTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):(HERE/'.selftest').mkdir(exist_ok=True)
 def test_exact_delta_and_complete_final_tree(self):
  baseline={'keep.txt':blob(b'unchanged'),'index.html':blob(b'old index'),'world-laws/jp-test.html':blob(b'old law')};raws={'index.html':'새 index'.encode(),'world-laws/jp-test.html':'<!doctype html>정정 이동'.encode(),'scripts/guard.mjs':b'// mock guard'};ops,target=compile_plan(baseline,raws,git_tree_entries(baseline)[0]);self.assertEqual(target['keep.txt'],baseline['keep.txt']);self.assertEqual(len(target),4);self.assertEqual(len(ops),3);self.assertEqual(ops[0]['kind'],'create-tree');self.assertEqual(ops[1]['kind'],'create-blob');self.assertEqual(ops[-1]['paths'],['index.html']);self.assertTrue(ops[-1]['completeTarget']);self.assertEqual(base64.b64decode(ops[1]['args']['content']),raws['index.html'])
  with tempfile.TemporaryDirectory(dir=HERE/'.selftest') as tmp:
   bare=Path(tmp)/'bare';subprocess.run(['git','init','--bare','-q',str(bare)],check=True);state=dict(baseline)
   for op in ops:
    self.assertLessEqual(max(op['requestFileBytes'],op['utf8WireBytes'])+RESERVE,CAP)
    if op['kind']=='create-tree':
     self.assertLessEqual(op['utf8WireBytes']+RESERVE,BUDGET);self.assertEqual(standard_tree(state,bare),op['expectedBaseTree'])
     for e in op['args']['tree_elements']:state[e['path']]=e.get('sha') or blob(e['content'].encode())
     self.assertEqual(standard_tree(state,bare),op['expectedResultTree'])
   self.assertEqual(state,target)
 def test_large_file_whole_blob_not_split(self):
  baseline={'keep':blob(b'x')};raw=('한글'*300000).encode();ops,target=compile_plan(baseline,{'world-laws/test.html':raw},git_tree_entries(baseline)[0]);self.assertEqual(len(ops),2);self.assertEqual(base64.b64decode(ops[0]['args']['content']),raw);self.assertTrue(ops[0]['wholeFileUnsplit']);self.assertEqual(ops[1]['args']['tree_elements'][0]['sha'],blob(raw));self.assertNotIn('content',ops[1]['args']['tree_elements'][0])
 def test_budget_and_base_fail_closed(self):
  baseline={'keep':blob(b'x')};tree=git_tree_entries(baseline)[0]
  with self.assertRaises(ValueError):compile_plan(baseline,{'a':b'x'},'0'*40)
  with self.assertRaises(ValueError):compile_plan(baseline,{'a':b'x'},tree,tree_budget=BUDGET+1)
  with self.assertRaises(ValueError):compile_plan(baseline,{'a':b'x'*10000},tree,tree_budget=RESERVE+100)
 def test_bounded_batch_and_no_completion_early(self):
  baseline={'index.html':blob(b'bootstrap'),'keep':blob(b'x')};raws={f'world-laws/jp-{i}.html':('mock'+str(i)).encode() for i in range(45)};raws['publication.json']=b'{}';ops,target=compile_plan(baseline,raws,git_tree_entries(baseline)[0]);trees=[x for x in ops if x['kind']=='create-tree'];self.assertEqual([x['entryCount'] for x in trees],[20,20,5,1]);self.assertTrue(all('publication.json' not in x['paths'] for x in trees[:-1]));self.assertEqual(trees[-1]['paths'],['publication.json'])
 def test_actual_javascript_wire_encoding(self):
  obj={'x':'한글\u2028</script>','y':'?x=a%26b#절'};wire=subprocess.check_output(['node','-e','let s="";process.stdin.on("data",x=>s+=x);process.stdin.on("end",()=>process.stdout.write(JSON.stringify(JSON.parse(s))));'],input=encode(obj,True));self.assertEqual(wire,encode(obj))
if __name__=='__main__':unittest.main()
