from alephclient import api
import pathlib
import email
import os
import json
import streamlit as st

ALEPH_HOST = "https://aleph.occrp.org/"

# ===========================================
#                 Aleph Utils
# ===========================================

def get_aleph():
  return api.AlephAPI(host=ALEPH_HOST, api_key=st.session_state.api_key)

# def upload_folders(file_types):
#   aleph = get_aleph()
#   parent_ids = {}
#   for file_type in file_types:
#     meta = {"title": file_type}
#     response = aleph.ingest_upload(st.session_state.collection_id, metadata=meta)
#     parent_ids[file_type] = response.get("id", None)
#   return parent_ids

def upload_files(file=None, meta=None):
  aleph = get_aleph()
  # Create file
  if file is not None:
    with open("file", "wb") as fd:
      fd.write(file)
    response = aleph.ingest_upload(st.session_state.collection_id, pathlib.Path("file"), metadata=meta)
    os.remove("file")
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

def process_pages(zipf, fname, upload_photo=False):
  message = get_message(zipf, fname)
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
      images.append((base64_image, meta))

  meta = get_meta(fname.split("?")[0], message['Subject'], content_location)
  response = upload_files(html_body, meta)
  if upload_photo and response.get("id"):
    parent_id = response['id']
    for base64_image, meta in images:
      meta['parent_id'] = parent_id
      upload_files(base64_image, meta)

def process_photos(zipf, fname):
  process_pages(zipf, fname, upload_photo=True)

def process_attachments(zipf, fname):
  if fname.endswith("/"):
    return
  
  case_data = json.loads(zipf.read("case_data/case_attachments.json")) 
  meta = get_meta(fname, fname.split("/")[-1], "")
  for i in case_data:
    if os.path.split(fname)[1] == i['Filename']:
      meta['source_url'] = i['Source']

  upload_files(zipf.read(fname), meta)