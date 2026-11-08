"""Literal catalog-response fixtures; these do not emulate PostgreSQL semantics."""
KEYS = (
 ('public.vams_effect_v3_provider_meta','p',('singleton',)),
 ('public.vams_effect_v3_provider_fences','p',('scope_id',)),
 ('public.vams_effect_v3_provider_objects','p',('operation_id',)),
 ('public.vams_effect_v3_provider_objects','u',('admission_digest',)),
 ('public.vams_effect_v3_provider_objects','u',('nonce',)),
 ('public.vams_effect_v3_provider_objects','u',('scope_id','resource_id')),
 ('public.vams_effect_v3_authority_meta','p',('singleton',)),
 ('public.vams_effect_v3_authority_scopes','p',('scope_id',)),
 ('public.vams_effect_v3_authority_operations','p',('operation_id',)),
 ('public.vams_effect_v3_authority_operations','u',('admission_digest',)),
 ('public.vams_effect_v3_authority_operations','u',('nonce',)),
 ('public.vams_effect_v4_authority_meta','p',('singleton',)),
 ('public.vams_effect_v4_authority_generations','p',('generation_id',)),
 ('public.vams_effect_v4_authority_generations','u',('scope_id','generation_id')),
 ('public.vams_effect_v4_authority_generations','u',('scope_id','ordinal')),
 ('public.vams_effect_v4_authority_heads','p',('scope_id',)),
 ('public.vams_effect_v4_authority_operations','p',('operation_id',)),
 ('public.vams_effect_v4_authority_operations','u',('admission_digest',)),
 ('public.vams_effect_v4_authority_operations','u',('nonce',)),
)

def unique_catalog_rows(tables):
    rows=[]
    for table,kind,columns in KEYS:
        if table not in tables:continue
        types=[21 if c=='singleton' else 20 if c=='ordinal' else 17 for c in columns]
        ops=[{21:'pg_catalog.int2_ops',20:'pg_catalog.int8_ops',17:'pg_catalog.bytea_ops'}[t] for t in types]
        rows.append((table,kind,list(columns),True,False,False,'r','p',
            True,True,True,True,True,len(columns),len(columns),True,True,True,
            [True]*len(columns),types,ops,True,True,True,True,True))
    return rows


FOREIGN_KEYS = (
 ('public.vams_effect_v3_provider_objects',('scope_id',),'public.vams_effect_v3_provider_fences',('scope_id',)),
 ('public.vams_effect_v3_authority_operations',('scope_id',),'public.vams_effect_v3_authority_scopes',('scope_id',)),
 ('public.vams_effect_v4_authority_generations',('scope_id','previous_generation'),'public.vams_effect_v4_authority_generations',('scope_id','generation_id')),
 ('public.vams_effect_v4_authority_heads',('scope_id','current_generation'),'public.vams_effect_v4_authority_generations',('scope_id','generation_id')),
 ('public.vams_effect_v4_authority_operations',('scope_id',),'public.vams_effect_v4_authority_heads',('scope_id',)),
 ('public.vams_effect_v4_authority_operations',('scope_id','generation_id'),'public.vams_effect_v4_authority_generations',('scope_id','generation_id')),
)


def foreign_key_catalog_rows(tables):
    return [(index + 101,child,list(columns),parent,list(references),True,True,False,False,'a','a','s',True)
        for index,(child,columns,parent,references) in enumerate(FOREIGN_KEYS)
        if child in tables or parent in tables]


def trigger_catalog_rows(tables):
    rows=[]
    for row in foreign_key_catalog_rows(tables):
        oid,child,_,parent=row[:4]
        for table,function,kind in (
            (child,'pg_catalog.RI_FKey_check_ins',5),(child,'pg_catalog.RI_FKey_check_upd',17),
            (parent,'pg_catalog.RI_FKey_noaction_del',9),(parent,'pg_catalog.RI_FKey_noaction_upd',17)):
            if table in tables:
                rows.append((table,oid,True,'O',function,kind,False,False,0,True,True,True))
    return rows


def additional_catalog_rows(query,tables):
    # Return literal fixture metadata for the explicitly requested projection.
    # This dispatch does not execute SQL, model native constraints or hold locks.
    if "WHERE c.contype='f'" in query:
        return foreign_key_catalog_rows(tables)
    if 'tr.tgconstraint::bigint' in query:
        return trigger_catalog_rows(tables)
    return None
