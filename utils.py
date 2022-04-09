from alephclient import api
import pathlib
import email
import os
import json
import streamlit as st
import random
import os

ALEPH_HOST = "https://aleph.occrp.org/"
FOLDERS_CACHE = {
  os.environ['HAITI_TEAM']: {"pages": os.environ['HAITI_TEAM_PAGES'], "photos": os.environ['HAITI_TEAM_PHOTOS']},
  os.environ['REPRO_RIGHTS'] : {"pages": os.environ['REPRO_RIGHTS_PAGES'], "photos": os.environ['REPRO_RIGHTS_PHOTOS']}
}

# ===========================================
#                 Aleph Utils
# ===========================================

def get_aleph():
  return api.AlephAPI(host=ALEPH_HOST, api_key=st.session_state.api_key)

def upload_folders(file_types):
  aleph = get_aleph()
  parent_ids = {}

  if st.session_state.collection_id in FOLDERS_CACHE:
    parent_ids = FOLDERS_CACHE[st.session_state.collection_id]
  else:
    # Get folders that exist
    stream = aleph.stream_entities({"id": st.session_state.collection_id})
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
      response = aleph.ingest_upload(st.session_state.collection_id, metadata=meta)
      parent_ids[f] = response.get("id", None)
  return parent_ids

def upload_files(file, meta, file_type):
  aleph = get_aleph()
  # Create file
  if file is not None:
    h = str(random.getrandbits(32))
    with open(h, "wb") as fd:
      fd.write(file)
    meta["parent_id"] = st.session_state.parent_ids[file_type]
    response = aleph.ingest_upload(st.session_state.collection_id, pathlib.Path(h), metadata=meta)
    os.remove(h)
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