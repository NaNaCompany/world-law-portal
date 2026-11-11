#!/usr/bin/env python3
"""Read-only comparison to historical fingerprints; never pads or alters files."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from build_release import files_digest,git_blob
from prepare_tree_packages import pure_tree,OLD_SITE_FP,OLD_FINAL_TREE
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',required=True);a=p.parse_args();root=Path(a.release);site=root/'sites/world-law-jp-01';_,fp=files_digest(root/'sites');files={p.relative_to(site).as_posix():git_blob(p.read_bytes()) for p in site.rglob('*') if p.is_file()};tree=pure_tree(files);print(json.dumps({'actualFiles':len(files),'actualSiteFingerprint':fp,'actualTree':tree,'historicalSiteFingerprint':OLD_SITE_FP,'historicalTree':OLD_FINAL_TREE,'siteMatches':fp==OLD_SITE_FP,'treeMatches':tree==OLD_FINAL_TREE,'byteIdentityClaim':fp==OLD_SITE_FP and tree==OLD_FINAL_TREE,'noFilesModified':True},indent=2))
