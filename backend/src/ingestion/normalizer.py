import re,unicodedata
def clean_text(value):
 if value is None:return None
 text=re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(value)).strip())
 return text or None
def normalize_legal_name(value):
 text=clean_text(value);return text.upper() if text else None
def normalize_identifier(value):
 text=clean_text(value);return re.sub(r'[\s-]+','',text).upper() if text else None
def normalize_record(row):
 lowered={re.sub(r'[^a-z0-9]+','_',str(k).strip().lower()).strip('_'):v for k,v in row.items()}
 def first(*keys):
  for key in keys:
   value=clean_text(lowered.get(key))
   if value:return value
  return None
 name=first('legal_name','company_name','business_name','name','entity_name')
 reg=first('registration_number','registration_no','reg_no','company_number','business_number','brs_number')
 pin=first('tax_pin','kra_pin','pin','taxpayer_pin')
 if not name:raise ValueError('Missing required legal name column or value')
 payload={str(k):clean_text(v) for k,v in lowered.items() if clean_text(v) is not None}
 return {'legal_name':name,'normalized_legal_name':normalize_legal_name(name),'registration_number':reg,'normalized_registration_number':normalize_identifier(reg),'tax_pin':pin,'normalized_tax_pin':normalize_identifier(pin),'status':(first('status','company_status','entity_status') or 'ACTIVE').upper(),'registry_payload':payload}
