// Sends links to the Video Downloader desktop app through its ytdl:// link handler.
// The extension collects no data and talks to no server.

const CONTEXTS = ["page", "link", "video", "audio"];
const MENU = [
  { id: "video", title: "Download video" },
  { id: "audio", title: "Download audio (MP3)" },
  { id: "options", title: "Download with options..." },
];

function send(tabId, url, mode) {
  if (!url || !/^https?:/i.test(url)) return;
  let link = "ytdl://?u=" + encodeURIComponent(url);
  if (mode) link += "&m=" + mode;
  chrome.tabs.update(tabId, { url: link });
}

// Toolbar button: the page you are on, with your saved settings
chrome.action.onClicked.addListener((tab) => send(tab.id, tab.url, ""));

// Right-click menu
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "root", title: "Video Downloader", contexts: CONTEXTS });
    for (const m of MENU) {
      chrome.contextMenus.create({ id: m.id, parentId: "root", title: m.title, contexts: CONTEXTS });
    }
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  send(tab.id, info.linkUrl || info.pageUrl, info.menuItemId);
});
