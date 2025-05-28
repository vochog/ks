chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "scanPdfs") {
        chrome.tabs.query({}, (tabs) => {
            const pdfUrls = tabs
                .filter(tab => tab.url && tab.url.toLowerCase().endsWith('.pdf'))
                .map(tab => tab.url);
            chrome.runtime.sendMessage({ action: "pdfUrlsScanned", urls: pdfUrls });
        });
    }
});