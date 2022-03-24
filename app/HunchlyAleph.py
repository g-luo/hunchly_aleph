import sys
import webbrowser
import subprocess

if __name__ == '__main__':
	# https://github.com/takumaw/jupyter-notebook-launcher-for-mac/blob/main/app/JupyterNotebookLauncher.py
    subprocess.Popen("streamlit run ../streamlit_app.py --server.port 1040", shell=True)
    webbrowser.open("http://localhost:1040")