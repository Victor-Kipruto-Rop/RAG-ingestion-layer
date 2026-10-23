import csv,io
def iter_csv_records(data:bytes,max_records:int):
 try:text=data.decode('utf-8-sig')
 except UnicodeDecodeError:text=data.decode('cp1252')
 try:dialect=csv.Sniffer().sniff(text[:8192],delimiters=',;\t|')
 except csv.Error:dialect=csv.excel
 reader=csv.DictReader(io.StringIO(text,newline=''),dialect=dialect)
 if not reader.fieldnames or not any((h or '').strip() for h in reader.fieldnames):raise ValueError('CSV has no usable header row')
 for row_number,row in enumerate(reader,start=2):
  if row_number-1>max_records:raise ValueError(f'CSV exceeds configured limit of {max_records} records')
  yield row_number,{str(k or '').strip():str(v or '').strip() for k,v in row.items() if k is not None}
