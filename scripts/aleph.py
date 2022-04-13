from alephclient import api
import pathlib
import email
import os
import json
from tqdm import tqdm
import sys
import zipfile
import random
import os

COLLECTION_ID = os.environ["COLLECTION_ID"]
if "FOLDERS_CACHE" in os.environ:
  FOLDERS_CACHE = json.load(open(os.environ["FOLDERS_CACHE"]))
else:
  FOLDERS_CACHE = {}

# Disable support for attachments since upload does not work
SUPPORTED_FILE_TYPES = {
  "pages/": ((".mhtml"), process_pages),
  "photos/": ((".jpg", ".jpeg", ".gif", ".png"), process_photos)
}
FILE_TYPES = ["pages/", "photos/"]
ALEPH_HOST = "https://aleph.occrp.org/"
# ===========================================
#                 Aleph Utils
# ===========================================

def delete_collections(collection_ids):
  aleph = get_aleph()
  failed = []
  for i in tqdm(collection_ids):
    try:
      aleph.delete_collection(i, sync=True)
    except:
      failed.append(i)
      continue

def get_aleph():
  return api.AlephAPI(host=ALEPH_HOST, api_key=os.environ["API_KEY"])

def upload_folders(file_types):
  aleph = get_aleph()
  parent_ids = {}

  if COLLECTION_ID in FOLDERS_CACHE:
    parent_ids = FOLDERS_CACHE[COLLECTION_ID]
  else:
    # Get folders that exist
    stream = aleph.stream_entities({"id": COLLECTION_ID})
    folders = [f for f in stream]
    for f in folders:
      if not f.get("properties", {}).get("title", None):
        continue
      title = f["properties"]["title"][0]
      if "id" in f and title in set(file_types):
        parent_ids[title] = f["id"]

  # Upload new folders
  for f in file_types:
    if f not in parent_ids:
      meta = {"title": f, "foreign_id": f}
      response = aleph.ingest_upload(COLLECTION_ID, metadata=meta)
      parent_ids[f] = response.get("id", None)
  return parent_ids

def upload_files(file, meta, file_type):
  aleph = get_aleph()
  # Create file
  hash = str(random.getrandbits(32))
  if file is not None:
    with open(hash, "wb") as fd:
      fd.write(file)
    meta["parent_id"] = PARENT_IDS[file_type]
    response = aleph.ingest_upload(COLLECTION_ID, pathlib.Path(hash), metadata=meta)
    os.remove(hash)
  return response

def create_collection(label, casefile=False, category="other", languages=[], summary=""):
  """
    Creates investigation.
  """
  aleph = get_aleph()
  data = {
    "label": label,
    "casefile": casefile,
    "category": category,
    "languages": languages,
    "summary": summary,
  }
  response = aleph.create_collection(data)
  return response

# ===========================================
#             Hunchly Processing
# ===========================================

def get_message(zipf, fname):
  file_contents = zipf.read(fname)
  message = email.message_from_bytes(file_contents)
  return message

def get_meta(file_name, title, source_url):
  meta = {}
  meta["file_name"] = file_name
  meta["title"] = title
  meta["generator"] = "Hunchly"
  meta["source_url"]= source_url
  return meta

def get_fname(fname):
  return fname.split("?")[0]

def walk(message, fname, file_type, upload_photo):
  html_body = b""
  content_location = None
  images = []
  for part in message.walk():
    if content_location == None:
      content_location = part["Content-Location"]

    content_type = part.get_content_type()
    if content_type == "multipart/related":
      continue

    if content_type == "text/plain" or content_type == "text/html":
      html_body += part.get_payload(decode=True)
    elif upload_photo and content_type.startswith("image/"):   
      image_path = part['Content-Location']
      base64_image = part.get_payload(decode=True)
      meta = get_meta(image_file, message['Subject'], image_path)
      upload_files(base64_image, meta, file_type)

  meta = get_meta(get_fname(fname), message['Subject'], content_location)
  upload_files(html_body, meta, file_type)

def process_pages(zipf, fname, file_type):
  message = get_message(zipf, fname)
  walk(message, fname, file_type, upload_photo=False)

def process_photos(zipf, fname, file_type):
  message = get_message(zipf, fname)
  walk(message, fname, file_type, upload_photo=True)

def process_attachments(zipf, fname, file_type):
  if fname.endswith("/"):
    return
  
  case_data = json.loads(zipf.read("case_data/case_attachments.json")) 
  meta = get_meta(fname, fname.split("/")[-1], "")
  for i in case_data:
    if os.path.split(fname)[1] == i['Filename']:
      meta['source_url'] = i['Source']

  upload_files(zipf.read(fname), meta, file_type)

def get_filelist(filelist, file_types):
  """
    Finds files with valid fname and groups by file_type.
  """
  filedict = {start: [] for start in file_types}
  for fname in filelist:
    for start in file_types:
      end, process_fn = SUPPORTED_FILE_TYPES[start]
      if fname.startswith(start) and fname.endswith(end):
        filedict[start].append((start, process_fn, fname))
  return sum(filedict.values(), [])

def process_hunchly(hunchly_export, file_types):
  zipf = zipfile.ZipFile(hunchly_export)
  filelist = zipf.namelist()
  filelist = get_filelist(filelist, file_types)
  missed_files = []
  # Use stqdm to show progress bar in Streamlit
  for start, process_fn, fname in tqdm(filelist):
    try:
      process_fn(zipf, fname, start)
    except Exception as e:
      print(e)
      missed_files.append(fname)
  json.dump(missed_files, open(f"error/{str(random.getrandbits(32))}.json", "w"))