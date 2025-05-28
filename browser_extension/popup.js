document.addEventListener('DOMContentLoaded', () => {
    const scanButton = document.getElementById('scanButton');
    const statusDiv = document.getElementById('status');
    const urlList = document.getElementById('urlList');

    scanButton.addEventListener('click', () => {
        statusDiv.textContent = 'Scanning...';
        urlList.innerHTML = '';
        chrome.runtime.sendMessage({ action: "scanPdfs" });
    });

    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === "pdfUrlsScanned") {
            if (request.urls.length > 0) {
                statusDiv.textContent = `Found ${request.urls.length} PDF tabs. Sending to Flask app...`;
                request.urls.forEach(url => {
                    const li = document.createElement('li');
                    li.textContent = url;
                    urlList.appendChild(li);
                });
                sendUrlsToFlask(request.urls);
            } else {
                statusDiv.textContent = 'No PDF tabs found.';
            }
        } else if (request.action === "flaskResponse") {
            if (request.status === "success") {
                statusDiv.textContent = `Success! View results: ${request.redirectUrl}`;
                chrome.tabs.create({ url: request.redirectUrl });
            } else {
                statusDiv.textContent = `Error: ${request.message}`;
                statusDiv.classList.add('error');
            }
        }
    });

    function sendUrlsToFlask(urls) {
        const keywords = prompt("Enter keywords to search (comma-separated):");
        if (!keywords) {
            chrome.runtime.sendMessage({ action: "flaskResponse", status: "error", message: "No keywords provided." });
            return;
        }
        const flaskAppUrl = `http://127.0.0.1:5000/process_pdfs?keywords=${encodeURIComponent(keywords)}`;

        fetch(flaskAppUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ pdf_urls: urls })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                statusDiv.textContent = `Success! View results: ${data.redirect_url}`;
                chrome.tabs.create({ url: `http://127.0.0.1:5000${data.redirect_url}` });
            } else {
                statusDiv.textContent = `Error: ${data.message || 'Unknown error'}`;
                statusDiv.classList.add('error');
            }
        })
        .catch(error => {
            console.error('Error sending URLs to Flask:', error);
            chrome.runtime.sendMessage({ action: "flaskResponse", status: "error", message: `Network error: ${error.message}` });
        });
    }
});