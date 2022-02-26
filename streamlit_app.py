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

def process_mhtml(zipf, fname):
  file_contents = zipf.read(fname)
  sha256hash = hashlib.sha256(file_contents).hexdigest()
  message = email.message_from_bytes(file_contents)
  html_body = b""
  
  content_location = None
  for part in message.walk():

    if content_location == None:
      content_location = part["Content-Location"]

    content_type = part.get_content_type()

    if content_type == "multipart/related":
      continue

    if content_type == "text/plain" or content_type == "text/html":
      html_body += part.get_payload(decode=True)
     
  # build a metadata object for aleph
  meta = {}
  meta["file_name"] = "{}.html".format(fname)
  meta["title"] = message['Subject']
  meta["generator"] = "Hunchly"
  meta["source_url"] = content_location
  
  with open("page.html", "wb") as fd:
    fd.write(html_body)
  response = upload_files("page.html", meta)
  os.path.remove("page.html")

def process_hunchly(hunchly_export):
  zipf = zipfile.ZipFile(hunchly_export)
  filelist = zipf.namelist()

  for fname in stqdm(filelist):
    if fname.endswith(".mhtml"):
      process_mhtml(zipf, fname)

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
    images or attachments. Export your Hunchly case, upload the zip file, input your Aleph API Key, and get the Aleph investigation 
    to upload to. Finally, click Submit and wait for the tool to upload all files.

    - To export your Hunchly Case: Open Hunchly, go to Export, and click "Export Case".
    - To get your Aleph API Key: Go to [Settings](https://aleph.occrp.org/settings), and copy "API Secret Access Key".
    - To create a new Aleph Investigation: Select "Create New Investigation" and inputting a name.

    Made with ❤️ in Berkeley by the [Berkeley Investigative Reporting Program](https://journalism.berkeley.edu/programs/mj/investigative-reporting/) (with source code
    from the Hunchly team).
  """

  st.set_page_config(page_title=title, page_icon=icon, layout="centered")
  st.title(icon + " " + title)
  st.markdown(body)

  # Upload Hunchly Case
  st.session_state.hunchly_export = st.file_uploader(
    "Upload Hunchly Case", 
    type=["zip"], 
    accept_multiple_files=False,
  )

  # Browse Aleph Investigations
  aleph_investigations = ["Create New Investigation"]

  if "option" not in st.session_state:
    st.session_state.investigation = aleph_investigations[0]
    st.session_state.new_investigation = ""
    st.session_state.collection_id = 0
    st.session_state.api_key = ""

  st.session_state.api_key = st.text_input("Input Aleph API Key")
  st.session_state.investigation = st.selectbox(
    "Browse Aleph Investigations",
    aleph_investigations,
  )

  # Disable if not creating new investigation
  create_new_investigation = st.session_state.investigation == aleph_investigations[-1]
  st.session_state.new_investigation = st.text_input(
    "Name Aleph Investigation",
    placeholder=st.session_state.investigation if not create_new_investigation else "", 
    disabled=(not create_new_investigation)
  )
  
  # Disable if no Hunchly zip or new investigation name is blank
  submitted = st.button(
    label="Submit",
    disabled=(not st.session_state.hunchly_export) or \
      (not st.session_state.api_key) or \
      (create_new_investigation and not st.session_state.new_investigation)
  )
  
  # TODO: get collections
  if submitted:
    if st.session_state.new_investigation:
      response = create_collection(st.session_state.new_investigation)
      st.session_state.collection_id = response["collection_id"]
    process_hunchly(st.session_state.hunchly_export)
    st.success("Success! Uploaded all HTML files to Aleph.")

if __name__ == "__main__":
  show_streamlit()