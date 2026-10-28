// CleanView inbox: a Google Apps Script that saves the "what CleanView learned" files
// people send from CleanView (and CleanListen) into a folder of your Google Drive, one per
// app ("CleanView learned", "CleanListen learned"). Nobody who sends needs a Google
// account: the app posts the file to this script's web address, and the script runs as
// you. Set up once (see tools/README-inbox.txt), then put the web app address in SEND_URL
// in cleanview_learn.py (and CleanListen's cleanlisten_learn.py).

var FOLDERS = {"CleanView": "CleanView learned", "CleanListen": "CleanListen learned"};
var MAX = 2000000;            // bytes; a real file is a few hundred KB at most

function doPost(e) {
  try {
    var body = e && e.postData ? e.postData.contents : "";
    if (!body || body.length > MAX) return reply(false, "empty or too big");
    var msg = JSON.parse(body);
    if (!FOLDERS.hasOwnProperty(msg.app) || !msg.data) {
      return reply(false, "not from CleanView or CleanListen");
    }
    var name = String(msg.name || msg.app + " learned.json")
        .replace(/[^\w .()\-]/g, "_").slice(0, 120);
    var stamp = Utilities.formatDate(new Date(), "UTC", "yyyy-MM-dd HH.mm.ss");
    folder(FOLDERS[msg.app]).createFile(stamp + " " + name, JSON.stringify(msg.data, null, 1),
                        "application/json");
    return reply(true);
  } catch (err) {
    return reply(false, String(err));
  }
}

// Opening the address in a browser shows this, to check it's running.
function doGet() {
  return reply(true, "The CleanView inbox is running.");
}

function folder(name) {
  var found = DriveApp.getFoldersByName(name);
  return found.hasNext() ? found.next() : DriveApp.createFolder(name);
}

function reply(ok, why) {
  return ContentService.createTextOutput(JSON.stringify({ok: ok, why: why || ""}))
      .setMimeType(ContentService.MimeType.JSON);
}
