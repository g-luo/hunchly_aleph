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

ALEPH_HOST = "https://aleph.occrp.org/"

class AlephUploader:
  def __init__(self, collection_id, api_key, folders_cache={}):
    self.collection_id = collection_id
    self.api_key = api_key
    self.folders_cache = folders_cache
    self.parent_ids = {}

  def delete_collections(self, collection_ids):
    aleph = self.get_aleph()
    failed = []
    for i in tqdm(collection_ids):
      try:
        aleph.delete_collection(i, sync=True)
      except:
        failed.append(i)
        continue

  def get_aleph(self):
    return api.AlephAPI(host=ALEPH_HOST, api_key=self.api_key)

  def upload_folders(self, file_types):
    aleph = self.get_aleph()
    parent_ids = {}

    if self.collection_id in self.folders_cache:
      parent_ids = self.folders_cache[self.collection_id]
    else:
      # Get folders that exist
      stream = aleph.stream_entities({"id": self.collection_id})
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
        response = aleph.ingest_upload(self.collection_id, metadata=meta)
        parent_ids[f] = response.get("id", None)
    return parent_ids

  def upload_files(self, file, meta, file_type):
    aleph = self.get_aleph()
    # Create file
    hash = str(random.getrandbits(32))
    if file is not None:
      with open(f"cache/{hash}", "wb") as fd:
        fd.write(file)
      meta["parent_id"] = self.parent_ids[file_type]
      response = aleph.ingest_upload(self.collection_id, pathlib.Path(f"cache/{hash}"), metadata=meta)
    return response

  def create_collection(self, label, casefile=False, category="other", languages=[], summary=""):
    """
      Creates investigation.
    """
    aleph = self.get_aleph()
    data = {
      "label": label,
      "casefile": casefile,
      "category": category,
      "languages": languages,
      "summary": summary,
    }
    response = aleph.create_collection(data)
    return response

  def get_message(self, zipf, fname):
    file_contents = zipf.read(fname)
    message = email.message_from_bytes(file_contents)
    return message

  def get_meta(self, file_name, title, source_url):
    meta = {}
    meta["file_name"] = file_name
    meta["title"] = title
    meta["generator"] = "Hunchly"
    meta["source_url"]= source_url
    return meta

  def get_fname(self, fname):
    return fname.split("?")[0]

  def walk(self, message, fname, file_type, upload_photo):
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
        meta = self.get_meta(image_file, message['Subject'], image_path)
        self.upload_files(base64_image, meta, file_type)

    meta = self.get_meta(self.get_fname(fname), message['Subject'], content_location)
    self.upload_files(html_body, meta, file_type)

  def process_pages(self, zipf, fname, file_type):
    message = self.get_message(zipf, fname)
    self.walk(message, fname, file_type, upload_photo=False)

  def process_photos(self, zipf, fname, file_type):
    message = self.get_message(zipf, fname)
    self.walk(message, fname, file_type, upload_photo=True)

  def process_attachments(self, zipf, fname, file_type):
    if fname.endswith("/"):
      return
    
    case_data = json.loads(zipf.read("case_data/case_attachments.json")) 
    meta = self.get_meta(fname, fname.split("/")[-1], "")
    for i in case_data:
      if os.path.split(fname)[1] == i['Filename']:
        meta['source_url'] = i['Source']

    self.upload_files(zipf.read(fname), meta, file_type)

  def get_filelist(self, filelist, file_types):
    """
      Finds files with valid fname and groups by file_type.
    """
    supported_file_types = {
      "pages/": ((".mhtml"), self.process_pages),
      "photos/": ((".jpg", ".jpeg", ".gif", ".png"), self.process_photos)
    }
    
    filedict = {start: [] for start in file_types}
    for fname in filelist:
      for start in file_types:
        end, process_fn = supported_file_types[start]
        if fname.startswith(start) and fname.endswith(end):
          filedict[start].append((start, process_fn, fname))
    return sum(filedict.values(), [])

  def process_hunchly(self, hunchly_export, file_types):
    # Setup caching for files and folders
    if not os.path.exists("cache"):
      os.mkdir("cache")
    self.parent_ids = self.upload_folders(file_types)

    # Process hunchly file
    zipf = zipfile.ZipFile(hunchly_export)
    filelist = zipf.namelist()
    filelist = self.get_filelist(filelist, file_types)
    # Use stqdm to show progress bar in Streamlit
    for start, process_fn, fname in tqdm(filelist):
      try:
        process_fn(zipf, fname, start)
      except Exception as e:
        print(e, fname)