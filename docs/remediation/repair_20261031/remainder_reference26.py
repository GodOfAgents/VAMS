"""Resource/value fixture arithmetic only; no Aiken, signatures or ledger validity.

Byte-string CBOR profile follows the public Plutus Data encoder documentation.
The prepared native controls must independently confirm the actual runner's bytes.
"""
from collections import Counter
import copy

ACTIONS=('create','vote','finalize_passed','finalize_rejected','cancel','queue','cancelintent','expireintent','executeintent','eighth_vote')
TOPOLOGY=('inputs_exact','inputs_global','outputs_exact','outputs_global','assets','datum_bytes','signers')

def data_bytes_cbor(payload):
    assert type(payload) is bytes
    def chunk(value):
        return (bytes([0x40+len(value)]) if len(value)<24 else b'\x58'+bytes([len(value)]))+value
    if len(payload)<=64: return chunk(payload)
    return b'\x5f'+b''.join(chunk(payload[i:i+64]) for i in range(0,len(payload),64))+b'\xff'

def val(ada, **tokens): return Counter({'ADA':ada,**tokens})
def frame(action):
    assert action in ACTIONS
    authority=val(5_000_000,AUTH=1)
    empty=val(3_000_000,P=1)
    one=val(4_000_000,P=1,VAMS=100,R0=1)
    result={'action':action,'fee':200_000,'signers':['a','b','p'] if action in ('create','queue','cancelintent','executeintent') else ['a'] if action in ('vote','eighth_vote') else ['p'],
        'lower':1000 if action in ('create','vote','cancel','eighth_vote') else 777_602_100 if action=='expireintent' else 2000,
        'upper':1100 if action in ('create','vote','cancel','eighth_vote') else 777_602_200 if action=='expireintent' else 2100,
        'inline_payloads':{},'datum_version':2,'destination':'expected'}
    if action=='create':
        inputs=[authority,val(5_000_000)]; outputs=[authority,empty,val(1_800_000)]; mint=Counter(P=1)
    elif action=='vote':
        inputs=[empty,val(5_000_000,VAMS=100)];outputs=[one,val(3_800_000)];mint=Counter(R0=1)
    elif action=='eighth_vote':
        before=val(10_000_000,P=1,VAMS=700,**{f'R{i}':1 for i in range(7)})
        after=val(11_000_000,P=1,VAMS=800,**{f'R{i}':1 for i in range(8)})
        inputs=[before,val(5_000_000,VAMS=100)];outputs=[after,val(3_800_000)];mint=Counter(R7=1)
    elif action=='finalize_passed':
        inputs=[one,val(1_000_000)];outputs=[one,val(800_000)];mint=Counter()
    elif action in ('finalize_rejected','cancel'):
        inputs=[one,val(1_000_000)];outputs=[val(1_000_000,VAMS=100),val(3_000_000),val(800_000)];mint=Counter(P=-1,R0=-1)
    elif action=='queue':
        inputs=[authority,one,val(1_000_000)];outputs=[authority,val(1_000_000,VAMS=100),val(3_000_000,INTENT=1),val(800_000)];mint=Counter(P=-1,R0=-1,INTENT=1)
    else:
        # Execute uses a non-executing terminal-intent stand-in, never an execution specification.
        inputs=[val(3_000_000,INTENT=1),val(1_000_000)];outputs=[val(3_000_000),val(800_000)];mint=Counter(INTENT=-1)
    result.update(inputs=copy.deepcopy(inputs),outputs=copy.deepcopy(outputs),mint=mint)
    return result

def conserves(value):
    total=Counter()
    for item in value['inputs']: total.update(item)
    for item in value['outputs']:
        for asset,amount in item.items(): total[asset]-=amount
    total.update(value['mint']);total['ADA']-=value['fee']
    return all(amount==0 for amount in total.values())

def mutate(action, variant, at_limit=False):
    result=frame(action)
    if variant in ('inputs_exact','inputs_global'):
        n=(16 if at_limit else 17)-len(result['inputs']) if variant=='inputs_global' else 1
        for _ in range(n): result['inputs'].append(val(2_000_000))
        result['outputs'][-1]['ADA']+=n*2_000_000
    elif variant in ('outputs_exact','outputs_global'):
        n=(16 if at_limit else 17)-len(result['outputs']) if variant=='outputs_global' else 1
        result['inputs'][-1]['ADA']+=n*2_000_000
        result['outputs'] += [val(2_000_000) for _ in range(n)]
    elif variant=='assets':
        for index in range(15 if at_limit else 16):
            name=f'AUX{index}'
            result['inputs'][-1][name]+=1;result['outputs'][-1][name]+=1
    elif variant=='datum_bytes':
        result['inline_payloads'][len(result['outputs'])-1]=bytes(866 if at_limit else 867)
    elif variant=='signers': result['signers']=list('abpde')+([] if at_limit else ['f'])
    elif variant=='datum_version':result['datum_version']=1
    elif variant=='destination':result['destination']='other'
    elif variant=='negative_window':result['lower'],result['upper']=-1,1
    elif variant=='before_deadline':result['lower'],result['upper']=1999,2000
    elif variant=='after_deadline':result['lower'],result['upper']=2001,2002
    elif variant=='create_at_deadline':result['lower'],result['upper']=2000,2100
    elif variant=='empty_window':result['lower']=result['upper']=2100
    elif variant=='before_execute':result['lower'],result['upper']=172_802_099,172_802_100
    elif variant=='maximum_width':result['inline_payloads'][0]=bytes(867)
    else:raise ValueError('unknown mutation')
    return result

def envelope_resource_subset(value):
    """Declared resource/window subset, not complete validator or ledger semantics."""
    return (1<=len(value['inputs'])<=16 and 1<=len(value['outputs'])<=16
        and len(value['signers'])<=5 and len(set(value['signers']))==len(value['signers'])
        and all(len([q for q in item.values() if q])<=16 for item in value['outputs'])
        and all(len(data_bytes_cbor(raw))<=896 for raw in value['inline_payloads'].values())
        and 0<=value['lower']<value['upper']<(1<<64) and value['upper']-value['lower']<=300_000)
