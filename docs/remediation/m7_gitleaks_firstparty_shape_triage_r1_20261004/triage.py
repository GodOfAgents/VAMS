import ast, collections, hashlib, json, math, pathlib, re
ROOT=pathlib.Path("/home/GodOfAgents/code/VAMS-testnet")
INPUT=ROOT/"docs/remediation/m7_gitleaks_current_r5_20261004/CURRENT-TREE-SANITIZED.json"
OUT=pathlib.Path("/home/GodOfAgents/vams-evidence/m7_gitleaks_shape_triage_r1_20261004")
OUT.mkdir(parents=True,exist_ok=True)
def sha(b): return hashlib.sha256(b).hexdigest()
def length_bucket(n):
    if n==0:return "0"
    if n<=16:return "1-16"
    if n<=31:return "17-31"
    if n<=63:return "32-63"
    if n==64:return "64"
    if n<=127:return "65-127"
    return "128+"
def shape(value):
    n=len(value)
    hx=bool(value) and all(c in "0123456789abcdefABCDEF" for c in value)
    if n>=12:
        counts=collections.Counter(value)
        ent=-sum((c/n)*math.log2(c/n) for c in counts.values())
        entropy="low" if ent<2 else "medium" if ent<4 else "high"
    else: entropy="not_assessed_short"
    return {"length_bucket":length_bucket(n),"is_hex":hx,"entropy_bucket":entropy}
SAFE_KEYS=frozenset({
    "schema","kind","name","type","field","value","sha256","hash","hex",
    "result","evidence","input","output","stdout","stderr","code","id",
    "status","count","phase","contract","function","args","payload","path",
    "file","source","target","owner","role","rule","line","start","end",
    "before","after","expected","actual","observed","version","network",
    "chain","address","proof","tx","transaction","block","height","timestamp",
    "duration","limit","mode","enabled","disabled","passed","failed","error",
    "warning","message","reason","category","class","method","test","case",
    "mutation","negative","positive","provider","validator","policy","config",
    "command","runner","tool","platform","compiler","binary","digest","nonce",
    "region","amount","token","key","secret","credential","signature","public",
    "private","script","status_code","returncode","exit_code","files","items",
    "records","entries","findings","inputs","outputs","checks","metadata"
})
def key_segment(key):
    s=str(key)
    if s in SAFE_KEYS: return s
    return "<opaque-key>"
def json_line_leaves(text):
    decoder=json.JSONDecoder()
    by_line=collections.defaultdict(list)
    line_starts=[0]+[i+1 for i,c in enumerate(text) if c=="\n"]
    import bisect
    def ws(pos):
        while pos<len(text) and text[pos].isspace(): pos+=1
        return pos
    def line_at(pos): return bisect.bisect_right(line_starts,pos)
    def parse(pos,pointer="$"):
        pos=ws(pos)
        if pos>=len(text): raise ValueError("unexpected end")
        ch=text[pos]
        if ch=="{":
            pos+=1
            while True:
                pos=ws(pos)
                if pos<len(text) and text[pos]=="}": return pos+1
                key,key_end=decoder.raw_decode(text,pos)
                if not isinstance(key,str): raise ValueError("non-string object key")
                pos=ws(key_end)
                if pos>=len(text) or text[pos] != ":": raise ValueError("missing colon")
                pos=parse(pos+1,pointer+"."+key_segment(key))
                pos=ws(pos)
                if pos<len(text) and text[pos]==",": pos+=1; continue
                if pos<len(text) and text[pos]=="}": return pos+1
                raise ValueError("malformed object")
        if ch=="[":
            pos+=1
            while True:
                pos=ws(pos)
                if pos<len(text) and text[pos]=="]": return pos+1
                pos=parse(pos,pointer+"[*]")
                pos=ws(pos)
                if pos<len(text) and text[pos]==",": pos+=1; continue
                if pos<len(text) and text[pos]=="]": return pos+1
                raise ValueError("malformed array")
        start=pos
        value,end=decoder.raw_decode(text,pos)
        if isinstance(value,str): item={"field":pointer,"value_type":"string",**shape(value)}
        elif value is None: item={"field":pointer,"value_type":"null"}
        elif isinstance(value,bool): item={"field":pointer,"value_type":"boolean"}
        elif isinstance(value,int): item={"field":pointer,"value_type":"integer"}
        elif isinstance(value,float): item={"field":pointer,"value_type":"number"}
        else: item={"field":pointer,"value_type":"other"}
        by_line[line_at(start)].append(item)
        return end
    pos=0
    while True:
        pos=ws(pos)
        if pos>=len(text): break
        pos=parse(pos)
    return by_line
def node_line_span(node):
    return getattr(node,"lineno",None),getattr(node,"end_lineno",getattr(node,"lineno",None))
def overlap(node,start,end):
    a,b=node_line_span(node)
    return a is not None and b is not None and a<=end and b>=start
data=json.loads(INPUT.read_bytes())
items=[]
unchanged_files=set()
changed_files=set()
for finding in data["first_party_findings"]:
    rel=finding["path"]
    pure=pathlib.PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts: raise RuntimeError("unsafe finding path")
    path=ROOT/rel
    expected=finding.get("file_sha256")
    try: raw=path.read_bytes()
    except OSError:
        items.append({"path":rel,"start_line":finding["start_line"],"end_line":finding["end_line"],"expected_file_sha256":expected,"source_identity":"missing_after_capture","analysis":"withheld"})
        changed_files.add(rel); continue
    actual=sha(raw)
    if not expected or actual!=expected:
        items.append({"path":rel,"start_line":finding["start_line"],"end_line":finding["end_line"],"expected_file_sha256":expected,"current_file_sha256":actual,"source_identity":"changed_after_capture","analysis":"withheld"})
        changed_files.add(rel); continue
    unchanged_files.add(rel)
    start,end=finding["start_line"],finding["end_line"]
    lines=raw.decode("utf-8",errors="replace").splitlines()
    if not isinstance(start,int) or not isinstance(end,int) or start<1 or end<start or end>len(lines):
        items.append({"path":rel,"start_line":start,"end_line":end,"expected_file_sha256":expected,"source_identity":"match","analysis":"invalid_line_range_withheld"})
        continue
    if pure.suffix.lower()==".json":
        try:
            by_line=json_line_leaves(raw.decode("utf-8"))
            candidate=[]
            for n in range(start,end+1): candidate.extend(by_line.get(n,[]))
            parse_status="full_json_line_spans"
        except Exception:
            candidate=[]
            parse_status="json_parse_failed_withheld"
        items.append({"path":rel,"start_line":start,"end_line":end,"file_sha256":expected,"source_identity":"match","analysis":"line_shape_only","line_parse_status":parse_status,"candidate_scalars":candidate})
    elif pure.suffix.lower()==".py":
        try:
            tree=ast.parse(raw.decode("utf-8"))
            node_counts=collections.Counter()
            literals=[]
            for node in ast.walk(tree):
                if overlap(node,start,end):
                    node_counts[type(node).__name__]+=1
                    if isinstance(node,ast.Constant) and isinstance(node.value,str): literals.append(shape(node.value))
            items.append({"path":rel,"start_line":start,"end_line":end,"file_sha256":expected,"source_identity":"match","analysis":"line_shape_only","ast_node_counts":dict(sorted(node_counts.items())),"candidate_string_literal_shapes":literals})
        except Exception:
            items.append({"path":rel,"start_line":start,"end_line":end,"file_sha256":expected,"source_identity":"match","analysis":"python_parse_failed"})
    else:
        items.append({"path":rel,"start_line":start,"end_line":end,"file_sha256":expected,"source_identity":"match","analysis":"unsupported_type_withheld"})
shape_counts=collections.Counter()
parse_counts=collections.Counter()
for item in items:
    if item.get("analysis")!="line_shape_only": continue
    if "candidate_scalars" in item:
        parse_counts[item["line_parse_status"]]+=1
        for scalar in item["candidate_scalars"]:
            shape_counts[(scalar["value_type"],scalar.get("length_bucket",""),str(scalar.get("is_hex","")),scalar.get("entropy_bucket",""))]+=1
    for s in item.get("candidate_string_literal_shapes",[]):
        shape_counts[("python_string",s["length_bucket"],str(s["is_hex"]),s["entropy_bucket"])]+=1
result={
 "schema":"m7-gitleaks-value-free-shape-triage-r1",
 "input_result_sha256":sha(INPUT.read_bytes()),
 "input_source_manifest_sha256":data["source_manifest_sha256_before"],
 "input_finding_count":len(data["first_party_findings"]),
 "source_identity_match_findings":sum(x.get("source_identity")=="match" for x in items),
 "source_changed_or_missing_findings":sum(x.get("source_identity") in ("changed_after_capture","missing_after_capture") for x in items),
 "source_files_unchanged":len(unchanged_files),
 "source_files_changed_or_missing":len(changed_files),
 "json_line_parse_status_counts":dict(sorted(parse_counts.items())),
 "candidate_shape_counts":[{"value_type":k[0],"length_bucket":k[1],"is_hex":k[2],"entropy_bucket":k[3],"occurrences":v} for k,v in sorted(shape_counts.items())],
 "findings":items,
 "limits":["The sanitizer records line ranges but no match columns; scalar shapes on a line are candidate context, not a confirmed matched value.","Shape, path, or field names do not adjudicate a finding or establish that a value is harmless.","Changed-after-capture files are not inspected; their finding identities are retained with analysis withheld.","This triage does not pass M0.4, satisfy T06, or constitute owner disposition."]
}
out=OUT/"TRIAGE.json"
out.write_text(json.dumps(result,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
print(json.dumps({k:result[k] for k in ["input_finding_count","source_identity_match_findings","source_changed_or_missing_findings","source_files_unchanged","source_files_changed_or_missing","json_line_parse_status_counts","candidate_shape_counts"]},sort_keys=True))

