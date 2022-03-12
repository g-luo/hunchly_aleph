import zipfile
from stqdm import stqdm
from utils import process_pages, process_photos, process_attachments
from utils import create_collection, upload_folders
import streamlit as st

# Disable support for attachments since upload does not work
SUPPORTED_FILE_TYPES = {
  "pages/": ((".mhtml"), process_pages),
  "photos/": ((".jpg", ".jpeg", ".gif", ".png"), process_photos),
  # "attachments/": ((""), process_attachments)
}

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
  # Use stqdm to show progress bar in Streamlit
  st.session_state.parent_ids = upload_folders(file_types)
  for start, process_fn, fname in stqdm(filelist):
    process_fn(zipf, fname, start)

# ===========================================
#             Streamlit GUI
# ===========================================
def show_streamlit():
  title = "Upload Hunchly to OCCRP Aleph"
  icon = "🔎"
  body = """
    **How-To Guide:**
    This web GUI takes your [Hunchly](https://www.hunch.ly) case and uploads it to 
    [OCCRP Aleph](https://aleph.occrp.org/). Export your Hunchly case, upload the zip file, input your Aleph API Key, and link the Aleph investigation to upload to. Finally, click Submit and wait for the tool to upload all files.

    - To export your Hunchly Case: Open Hunchly, go to Export, and click "Export Case".
    - To get your Aleph API Key: Go to [Settings](https://aleph.occrp.org/settings), and copy "API Secret Access Key".
    - To link a Aleph Investigation: Go to [Investigations](https://aleph.occrp.org/investigations), select one, and input the link that appears in the top bar. \
    To create a new investigation, input a new name instead of a link.

    Made with ❤️ in Berkeley by the [Berkeley Investigative Reporting Program](https://journalism.berkeley.edu/programs/mj/investigative-reporting/) and [Human Rights Center](https://humanrights.berkeley.edu/home) (with source code
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
  if "file_types" not in st.session_state:
    st.session_state.file_types = [False for f in SUPPORTED_FILE_TYPES.keys()]

  st.write("Select Folders to Upload")
  for i, f in enumerate(SUPPORTED_FILE_TYPES.keys()):
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
    
    file_types = [f for i, f in enumerate(SUPPORTED_FILE_TYPES.keys()) if st.session_state.file_types[i]]
    process_hunchly(st.session_state.hunchly_export, file_types)
    st.success("Success! Uploaded all HTML files to Aleph.")

if __name__ == "__main__":
  show_streamlit()