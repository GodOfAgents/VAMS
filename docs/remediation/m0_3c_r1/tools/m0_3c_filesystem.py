"""Descriptor-bound immutable evidence snapshots for M0.3c artifacts."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat

class EvidenceTreeError(RuntimeError):
    pass

def _canonical_relative(name: str) -> str:
    if not isinstance(name,str) or not name or "\\" in name or "\x00" in name:
        raise EvidenceTreeError("filesystem.path")
    try:name.encode("ascii")
    except UnicodeEncodeError as exc:raise EvidenceTreeError("filesystem.path") from exc
    p=PurePosixPath(name)
    if p.is_absolute() or any(x in {"",".",".."} for x in name.split("/")):
        raise EvidenceTreeError("filesystem.path")
    return name

def _allowed_directories(files:set[str])->set[str]:
    out=set()
    for name in files:
        for parent in PurePosixPath(name).parents:
            if str(parent)!=".":out.add(parent.as_posix())
    return out

@dataclass(frozen=True)
class EntryIdentity:
    device:int
    inode:int
    mode:int
    links:int
    size:int
    mtime_ns:int
    ctime_ns:int
    def tuple(self):
        return (self.device,self.inode,self.mode,self.links,self.size,self.mtime_ns,self.ctime_ns)

def _identity(value)->EntryIdentity:
    return EntryIdentity(value.st_dev,value.st_ino,value.st_mode,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns)

class ArtifactSnapshot:
    """One-open immutable bytes plus descriptor-relative lifecycle verification."""
    def __init__(self,root:Path,allowed_files:set[str],manifest_name="SHA256SUMS",per_file_limit=2_097_152,total_limit=33_554_432):
        self.root=Path(root)
        self.expected={_canonical_relative(x) for x in allowed_files|{manifest_name}}
        self.directories=_allowed_directories(self.expected)
        self.per_file_limit=per_file_limit
        self.total_limit=total_limit
        self._bytes={}
        self._identity={}
        self._dirfds={}
        self._closed=False
        self._parent_fd=None
        self._root_name=self.root.name
        self._capture()
    def _capture(self):
        parent=self.root.parent
        flags=os.O_RDONLY|getattr(os,"O_DIRECTORY",0)|getattr(os,"O_NOFOLLOW",0)
        self._parent_fd=os.open(parent,flags)
        before=os.stat(self._root_name,dir_fd=self._parent_fd,follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode):
            raise EvidenceTreeError("filesystem.root")
        root_fd=os.open(self._root_name,flags,dir_fd=self._parent_fd)
        after=os.fstat(root_fd)
        if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):
            os.close(root_fd);raise EvidenceTreeError("filesystem.race")
        self._root_identity=_identity(after)
        self._dirfds[""]=root_fd
        seen={(after.st_dev,after.st_ino)}
        total=0
        def walk(fd,prefix):
            nonlocal total
            count=0
            with os.scandir(fd) as entries:
                for entry in entries:
                    rel=_canonical_relative((prefix+"/"+entry.name) if prefix else entry.name)
                    before=entry.stat(follow_symlinks=False); mode=before.st_mode
                    if stat.S_ISLNK(mode):raise EvidenceTreeError("filesystem.symlink")
                    if stat.S_ISDIR(mode):
                        if rel not in self.directories:raise EvidenceTreeError("filesystem.directory")
                        child=os.open(entry.name,flags,dir_fd=fd); opened=os.fstat(child)
                        if (before.st_dev,before.st_ino)!=(opened.st_dev,opened.st_ino):
                            os.close(child);raise EvidenceTreeError("filesystem.race")
                        ident=(opened.st_dev,opened.st_ino)
                        if ident in seen:os.close(child);raise EvidenceTreeError("filesystem.inode_alias")
                        seen.add(ident);self._dirfds[rel]=child;self._identity[rel]=_identity(opened)
                        children=walk(child,rel)
                        if children==0:raise EvidenceTreeError("filesystem.empty_directory")
                        count+=1;continue
                    if not stat.S_ISREG(mode):raise EvidenceTreeError("filesystem.special")
                    if rel not in self.expected:raise EvidenceTreeError("filesystem.file")
                    if before.st_nlink!=1:raise EvidenceTreeError("filesystem.hardlink")
                    ident=(before.st_dev,before.st_ino)
                    if ident in seen:raise EvidenceTreeError("filesystem.inode_alias")
                    fflags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)
                    file_fd=os.open(entry.name,fflags,dir_fd=fd)
                    try:
                        opened=os.fstat(file_fd)
                        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink!=1 or (before.st_dev,before.st_ino)!=(opened.st_dev,opened.st_ino):
                            raise EvidenceTreeError("filesystem.race")
                        if opened.st_size<0 or opened.st_size>self.per_file_limit or total+opened.st_size>self.total_limit:
                            raise EvidenceTreeError("filesystem.bounds")
                        remaining=opened.st_size;parts=[]
                        while remaining:
                            chunk=os.read(file_fd,min(131072,remaining))
                            if not chunk:raise EvidenceTreeError("filesystem.short_read")
                            parts.append(chunk);remaining-=len(chunk)
                        if os.read(file_fd,1):raise EvidenceTreeError("filesystem.growth")
                        final=os.fstat(file_fd)
                        if _identity(opened).tuple()!=_identity(final).tuple():raise EvidenceTreeError("filesystem.race")
                    finally:os.close(file_fd)
                    data=b"".join(parts);total+=len(data);seen.add(ident)
                    self._bytes[rel]=data;self._identity[rel]=_identity(final);count+=1
            return count
        try:walk(root_fd,"")
        except Exception:
            self.close();raise
        if set(self._bytes)!=self.expected or set(self._dirfds)-{""}!=self.directories:
            self.close();raise EvidenceTreeError("filesystem.topology")
    def get_bytes(self,name:str)->bytes:
        if self._closed:raise EvidenceTreeError("filesystem.closed")
        name=_canonical_relative(name)
        if name not in self._bytes:raise EvidenceTreeError("filesystem.file")
        return self._bytes[name]
    def digest(self,name:str)->str:
        return hashlib.sha256(self.get_bytes(name)).hexdigest()
    def _rescan(self):
        observed={}
        dirs=set()
        for prefix,fd in self._dirfds.items():
            with os.scandir(fd) as entries:
                count=0
                for entry in entries:
                    rel=_canonical_relative((prefix+"/"+entry.name) if prefix else entry.name)
                    value=entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(value.st_mode):raise EvidenceTreeError("filesystem.symlink")
                    observed[rel]=_identity(value);count+=1
                if prefix and count==0:raise EvidenceTreeError("filesystem.empty_directory")
        return observed
    def verify_stable(self):
        if self._closed:raise EvidenceTreeError("filesystem.closed")
        root_now=os.stat(self._root_name,dir_fd=self._parent_fd,follow_symlinks=False)
        root_open=os.fstat(self._dirfds[""])
        if self._root_identity.tuple()!=_identity(root_now).tuple() or self._root_identity.tuple()!=_identity(root_open).tuple():
            raise EvidenceTreeError("filesystem.race")
        observed=self._rescan()
        expected=set(self._identity)
        if set(observed)!=expected:raise EvidenceTreeError("filesystem.topology")
        for name in expected:
            if observed[name].tuple()!=self._identity[name].tuple():
                raise EvidenceTreeError("filesystem.race")
        return True
    def close(self):
        if self._closed:return
        for fd in list(self._dirfds.values())[::-1]:
            try:os.close(fd)
            except OSError:pass
        self._dirfds.clear()
        if self._parent_fd is not None:
            try:os.close(self._parent_fd)
            except OSError:pass
            self._parent_fd=None
        self._closed=True
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

def capture_exact_tree(root:Path,allowed_files:set[str],manifest_name="SHA256SUMS",per_file_limit=2_097_152,total_limit=33_554_432):
    return ArtifactSnapshot(root,allowed_files,manifest_name,per_file_limit,total_limit)

def inspect_exact_tree(root:Path,allowed_files:set[str],manifest_name="SHA256SUMS")->dict[str,str]:
    with capture_exact_tree(root,allowed_files,manifest_name) as snapshot:
        result={name:snapshot.digest(name) for name in snapshot.expected}
        snapshot.verify_stable()
        return result
