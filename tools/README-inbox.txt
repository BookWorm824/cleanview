Setting up the CleanView inbox (once, about 5 minutes)

The "Send what CleanView learned" and "Send what we refined" buttons send their file
straight to a folder in your Google Drive called "CleanView learned" (CleanListen's go to
"CleanListen learned"; the same script and address serve both). Only you set this up;
nobody who presses the buttons needs a Google account.

1. Go to https://script.google.com and sign in with your Google account.
2. Press "New project". Name it "CleanView inbox" (click "Untitled project" at the top).
3. Delete what's in the editor, and paste in everything from tools/cleanview_inbox.gs.
   Press the save icon.
4. Press "Deploy" (top right), then "New deployment".
5. Next to "Select type", press the gear and choose "Web app".
6. Set "Execute as" to "Me", and "Who has access" to "Anyone". Press "Deploy".
7. Google asks for permission to use your Drive: press "Authorize access", pick your
   account. If it says "Google hasn't verified this app", press "Advanced", then
   "Go to CleanView inbox (unsafe)" (it's your own script), then "Allow".
8. Copy the "Web app" address (it ends in /exec) and send it to Claude.
   Opening that address in a browser should say "The CleanView inbox is running."

Files then arrive in "CleanView learned" in your Drive, named with the date and time.
To add them to CleanView, download them and ask Claude to merge them
(tools/merge_learned.py into shared_learned.json) and release an update.

If you ever change the script, use Deploy > Manage deployments > edit (pencil) > Version:
New version, so the address stays the same.
