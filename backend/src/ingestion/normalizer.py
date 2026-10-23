import re,unicodedata
def clean_text(value):
 if value is None:return None
 text=re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(value)).strip())
 return text or None
def normalize_legal_name(value):
 text=clean_text(value);return text.upper() if text else None
def normalize_identifier(value):
 text=clean_text(value);return re.sub(r'[\s-]+','',text).upper() if text else None
_PERSONAL_FIELD_TOKENS={'director','directors','shareholder','shareholders','owner','owners','individual','person','first_name','middle_name','last_name','email','phone','mobile','national_id','passport','date_of_birth','dob','residential','personal','contact_person','id_number','identity_number'}
_CORPORATE_COMPLIANCE_FIELDS={'company_status','entity_status','compliance_status','compliance_flag','corporate_risk_flag','risk_flag','sanctions_status','watchlist_status','company_compliance_flag'}
def _is_personal_payload_field(key):
 normalized=re.sub(r'[^a-z0-9]+','_',str(key).strip().lower()).strip('_')
 if normalized in _CORPORATE_COMPLIANCE_FIELDS:return False
 parts=set(normalized.split('_'))
 return any(token in parts or token in normalized for token in _PERSONAL_FIELD_TOKENS)

PERSONAL_PAYLOAD_TOKENS={'director','shareholder','owner','individual','person','first_name','middle_name','last_name','email','phone','mobile','national_id','passport','date_of_birth','dob','residential','personal','contact_person','id_number','identity_number'}
CORPORATE_FLAG_FIELDS={'company_status','entity_status','compliance_status','compliance_flag','corporate_risk_flag','risk_flag','sanctions_status','watchlist_status','company_compliance_flag'}
def is_personal_payload_field(key):
 normalized=re.sub(r'[^a-z0-9]+','_',str(key).strip().lower()).strip('_')
 if normalized in CORPORATE_FLAG_FIELDS:return False
 parts=set(normalized.split('_'))
 return any(token in parts or token in normalized for token in PERSONAL_PAYLOAD_TOKENS)

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
 payload={str(k):clean_text(v) for k,v in lowered.items() if clean_text(v) is not None and not _is_personal_payload_field(k)}
 return {'legal_name':name,'normalized_legal_name':normalize_legal_name(name),'registration_number':reg,'normalized_registration_number':normalize_identifier(reg),'tax_pin':pin,'normalized_tax_pin':normalize_identifier(pin),'status':(first('status','company_status','entity_status') or 'UNKNOWN').upper(),'registry_payload':payload}
