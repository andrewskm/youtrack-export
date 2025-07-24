# YouTrack Export

A project that allows the extract of full YouTrack issue data including custom attributes, comments, and attachments.

## How to Run

1. Install dependencies 
2. (Optional) Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python app.py
   ```
4. Follow the prompts for exporting. 


## Features
- Can select all projects or specific projects to export
- Exports all issue fields including custom project fields
- Only extract unresolved tasks 
- Apply custom query to be appended to the request
- Extracts comments and attachments


## Storage 
All extracted data is stored in the `exports` folder grouped by project.
