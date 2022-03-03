import email
import hashlib
import zipfile
import pathlib
import os

import streamlit as st
from stqdm import stqdm
from alephclient import api

aleph_host = "https://aleph.occrp.org/"

# ===========================================
#                 Aleph Utils
# ===========================================

def get_aleph():
  return api.AlephAPI(host=aleph_host,api_key=st.session_state.api_key)

def upload_files(file_path=None, metadata=None):
  aleph = get_aleph()
  if file_path is not None:
    response = aleph.ingest_upload(st.session_state.collection_id, pathlib.Path(file_path), metadata=metadata)
  else:
    response = aleph.ingest_upload(st.session_state.collection_id, metadata=metadata)
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

def get_collections(query=""):
  aleph = get_aleph()
  response = aleph.filter_collections(query)
  return response.result

# ===========================================
#             Hunchly Processing
# ===========================================

def process_pages(zipf, fname, upload_photo=False):
  file_contents = zipf.read(fname)
  sha256hash = hashlib.sha256(file_contents).hexdigest()
  message = email.message_from_bytes(file_contents)
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
      # extract the image and then send it off for processing
      base64_image = part.get_payload(decode=True)
      image_file = image_path.split("/")[-1]
      meta = {}
      meta["file_name"] = image_file
      meta['title'] = message['Subject']
      meta['generator'] = "Hunchly"
      meta['source_url']= image_path
      images.append((base64_image, image_file, meta))
     
  # Build a metadata object for aleph
  meta = {}
  meta["file_name"] = fname.split("?")[0]
  meta["title"] = message['Subject']
  meta["generator"] = "Hunchly"
  meta["source_url"] = content_location
  
  # Upload html
  with open("page.html", "wb") as fd:
    fd.write(html_body)
  response = upload_files("page.html", meta)
  os.remove("page.html")

  if upload_photo and response.get("id") != None:
    parent_id = response['id']
    for image in images:
      image[2]['parent_id'] = parent_id
      with open(image[1],"wb") as fd:
        fd.write(image[0])
      upload_files(image[1], image[2])
      os.remove(image[1])

def process_photos(zipf, fname):
  process_pages(zipf, fname, upload_photo=True)

def process_attachments(zipf, fname):
  case_data = json.loads(zipf.read("case_data/case_attachments.json"))
  meta = {}
  meta["file_name"] = fname
  meta["generator"] = "Hunchly"       
  file_path = os.path.split(fname)[1]
  for i in case_data:
    if file_path == i['Filename']:
      meta['source_url'] = i['Source']
  upload_files(zipf.read(fname), fname, meta)

def process_hunchly(hunchly_export, file_types):
  zipf = zipfile.ZipFile(hunchly_export)
  filelist = zipf.namelist()
  filelist = [fname for fname in filelist if fname.startswith(tuple(file_types))]

  # Use stqdm to show progress bar in Streamlit
  for fname in stqdm(filelist):
    if fname.startswith("pages/"):
      process_pages(zipf, fname)
    elif fname.startswith("photos/"):
      process_photos(zipf, fname)
    elif fname.startswith("attachments/"):
      process_attachments(zipf, fname)

# ===========================================
#             Streamlit GUI
# ===========================================
def show_streamlit():
  title = "Upload Hunchly to OCCRP Aleph"
  icon = "🔎"
  body = """
    **How-To Guide:**
    This web GUI takes your [Hunchly](https://www.hunch.ly) case and uploads it to 
    [OCCRP Aleph](https://aleph.occrp.org/). Note that it only uploads mhtml files and does NOT process
    images or attachments. Export your Hunchly case, upload the zip file, input your Aleph API Key, and link the Aleph investigation 
    to upload to. Finally, click Submit and wait for the tool to upload all files.

    - To export your Hunchly Case: Open Hunchly, go to Export, and click "Export Case".
    - To get your Aleph API Key: Go to [Settings](https://aleph.occrp.org/settings), and copy "API Secret Access Key".
    - To link a Aleph Investigation: Go to [Investigations](https://aleph.occrp.org/investigations), select one, and input the link that appears in the top bar. \
    To create a new investigation, input a new name instead of a link.

    Made with ❤️ in Berkeley by Grace Luo in collaboration with the [Berkeley Investigative Reporting Program](https://journalism.berkeley.edu/programs/mj/investigative-reporting/) (with source code
    from the Hunchly team).
  """

  st.set_page_config(page_title=title, page_icon=icon, layout="centered")
  st.title(icon + " " + title)
  st.markdown(body)

  if "option" not in st.session_state:
    st.session_state.investigation = ""
    st.session_state.collection_id = 0
    st.session_state.api_key = ""

  # Upload Hunchly Case
  st.session_state.hunchly_export = st.file_uploader(
    "Upload Hunchly Case", 
    type=["zip"], 
    accept_multiple_files=False,
  )

  # Select File Types
  file_types = ["pages/", "photos/", "attachments/"]
  if "file_types" not in st.session_state:
    st.session_state.file_types = [False for f in file_types]

  st.write("Select Folders to Upload")
  for i, f in enumerate(file_types):
    st.session_state.file_types[i] = st.checkbox(f, value=True)

  # Input Aleph API Key
  st.session_state.api_key = st.text_input("Input Aleph API Key")

  # Input Aleph Investigation Link
  st.session_state.investigation = st.text_input(
    "Link Aleph Investigation",
    placeholder="https://aleph.occrp.org/investigations/0 OR New Investigation Name"
  )
  
  # Disable if no Hunchly zip or new investigation name is blank
  submitted = st.button(
    label="Submit",
    disabled=(not st.session_state.hunchly_export) or \
      (not st.session_state.api_key) or \
      (not st.session_state.investigation)
  )
  
  if submitted:
    if "aleph.occrp.org" not in st.session_state.investigation:
      response = create_collection(st.session_state.investigation)
      st.session_state.collection_id = response["collection_id"]
    else:
      st.session_state.collection_id = st.session_state.investigation.split("/")[-1]
    
    process_hunchly(st.session_state.hunchly_export, [f for i, f in enumerate(file_types) if st.session_state.file_types[i]])
    st.success("Success! Uploaded all HTML files to Aleph.")

if __name__ == "__main__":
  show_streamlit()