# 🔎 Upload Hunchly to OCCRP Aleph

**How-To Guide:**
This web GUI takes your [Hunchly](https://www.hunch.ly) case and uploads it to 
[OCCRP Aleph](https://aleph.occrp.org/). Export your Hunchly case, upload the zip file, input your Aleph API Key, and link the Aleph investigation to upload to. Finally, click Submit and wait for the tool to upload all files.

- To export your Hunchly Case: Open Hunchly, go to Export, and click "Export Case".
- To get your Aleph API Key: Go to [Settings](https://aleph.occrp.org/settings), and copy "API Secret Access Key".
- To link a Aleph Investigation: Go to [Investigations](https://aleph.occrp.org/investigations), select one, and input the link that appears in the top bar. \
To create a new investigation, input a new name instead of a link.

Made with ❤️ in Berkeley by the [Berkeley Investigative Reporting Program](https://journalism.berkeley.edu/programs/mj/investigative-reporting/) and [Human Rights Center](https://humanrights.berkeley.edu/home) (with source code
from the Hunchly team).

<img width="583" alt="screenshot" src="gui.png">

**Packaging as a Mac App**
To package this library as a Mac App, do the following:
```
cd app
python3 -m venv env
source env/bin/activate
pip install -r ../requirements.txt
pip install py2app
python3 setup.py py2app
```

Note that the files `setup.py` and `HunchlyAleph.py` were specifically created for this packaging process. Some fixes include increasing the max recursion depth as a workaround for a bug in modulegraph / ast, and using webbrowser to ensure a window pops up after the shell script is run. You may also need to link .dylib files that have different names or change your active python version to python3.