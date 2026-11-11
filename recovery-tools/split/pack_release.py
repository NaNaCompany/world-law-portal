"""Recovered deterministic archive helper only; no full-release packing entry point."""
import gzip,io,tarfile,sys
from pathlib import Path
sys.dont_write_bytecode=True
def deterministic_archive(site,target):
 site=Path(site);target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
 with target.open('wb') as f,gzip.GzipFile(filename='',fileobj=f,mode='wb',mtime=0) as gz,tarfile.open(fileobj=gz,mode='w') as tar:
  for p in sorted(site.rglob('*')):
   if p.is_symlink():raise ValueError('Refusing symlink archive member')
   if not p.is_file():continue
   raw=p.read_bytes();info=tarfile.TarInfo(p.relative_to(site).as_posix());info.size=len(raw);info.mode=0o644;info.mtime=0;info.uid=info.gid=0;tar.addfile(info,io.BytesIO(raw))
if __name__=='__main__':raise SystemExit('PAUSED: full split packer is not restored; use explicit phase1 packer')
