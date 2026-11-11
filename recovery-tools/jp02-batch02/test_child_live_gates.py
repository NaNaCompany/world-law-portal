"""Synthetic identity/tree mutation tests against actual checker gate functions."""
import ast,copy,pathlib,sys,unittest
sys.dont_write_bytecode=True
W=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(W.parent/'root190-tools'));from root190_common import git_tree_entries
source=ast.parse((W/'check_child_live.py').read_text());nodes=[x for x in source.body if isinstance(x,ast.FunctionDef) and x.name in ['validate_git_identity','validate_complete_tree']];assert len(nodes)==2
ns={'git_tree_entries':git_tree_entries};exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-checker-gates>','exec'),ns)
class Gates(unittest.TestCase):
 def setUp(self):
  self.blobs={'a':'1'*40,'sub/b':'2'*40};self.tree,self.entries=git_tree_entries(self.blobs);self.e={'commit':'a'*40,'tree':self.tree,'runId':99,'runUrl':'https://github.com/NaNaCompany/world-law-jp-02/actions/runs/99'};self.snap={'ref':{'ref':'refs/heads/main','object':{'type':'commit','sha':'a'*40}},'gitCommit':{'sha':'a'*40,'tree':{'sha':self.tree}},'gitTree':{'sha':self.tree,'truncated':False},'deployment':{'id':99,'head_branch':'main','html_url':self.e['runUrl'],'head_sha':'a'*40,'status':'completed','conclusion':'success','name':'pages build and deployment'}}
 def check(self):ns['validate_git_identity'](self.e,self.snap);ns['validate_complete_tree'](self.entries,self.blobs,self.tree)
 def test_positive(self):self.check()
 def test_commit_identity(self):
  self.snap['gitCommit']['sha']='b'*40
  with self.assertRaises(AssertionError):self.check()
 def test_ref_identity(self):
  self.snap['ref']['ref']='refs/heads/other'
  with self.assertRaises(AssertionError):self.check()
 def test_run_identity(self):
  for k,v in [('id',100),('head_branch','other'),('html_url','https://example.org'),('head_sha','b'*40)]:
   original=self.snap['deployment'][k];self.snap['deployment'][k]=v
   with self.assertRaises(AssertionError):self.check()
   self.snap['deployment'][k]=original
 def test_duplicate_path(self):
  self.entries.append(copy.deepcopy(self.entries[0]))
  with self.assertRaises(AssertionError):self.check()
 def test_unexpected_type(self):
  self.entries.append({'path':'other','mode':'160000','type':'commit','sha':'3'*40})
  with self.assertRaises(AssertionError):self.check()
 def test_directory_mode(self):
  next(x for x in self.entries if x['type']=='tree')['mode']='100644'
  with self.assertRaises(AssertionError):self.check()
 def test_directory_sha(self):
  next(x for x in self.entries if x['type']=='tree')['sha']='3'*40
  with self.assertRaises(AssertionError):self.check()
 def test_missing_directory(self):
  self.entries=[x for x in self.entries if x['type']!='tree']
  with self.assertRaises(AssertionError):self.check()
if __name__=='__main__':unittest.main()
