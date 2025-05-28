import os
import json
import requests
from PyPDF2 import PdfReader
from flask import Flask, request, jsonify, render_template, redirect, url_for
import re
from urllib.parse import quote_plus, urlparse, urlunparse

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'downloads' # For temporarily storing PDFs
app.config['SEARCH_RESULTS_FILE'] = 'output.json'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global variable to store search results for reporting
search_results = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_pdfs', methods=['POST'])
def process_pdfs():
    global search_results # Declare as global to modify it

    data = request.get_json()
    pdf_urls = data.get('pdf_urls', [])
    search_keywords = request.args.get('keywords') # Keywords will be passed via URL if you scan from main app

    if not pdf_urls:
        return jsonify({"status": "error", "message": "No PDF URLs provided."}), 400

    # For now, let's hardcode keywords for demonstration or add a form on index.html
    # In a real app, you'd get these from user input on your Flask app's main page
    # or from the browser extension popup if you enhance it.
    if not search_keywords:
        # If no keywords from URL, use a default for testing
        search_keywords = request.form.get('keywords', 'python,flask,pdf,data,report') # Get from form if direct submission
        if not search_keywords:
            return jsonify({"status": "error", "message": "No search keywords provided."}), 400

    keywords = [k.strip().lower() for k in search_keywords.split(',')]

    # Clear previous results
    search_results = []

    for pdf_url in pdf_urls:
        try:
            print(f"Processing PDF: {pdf_url}")
            response = requests.get(pdf_url, stream=True, timeout=10)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

            # Sanitize filename for local storage
            parsed_url = urlparse(pdf_url)
            filename = os.path.basename(parsed_url.path)
            if not filename:
                filename = "downloaded_pdf.pdf"
            local_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            with open(local_pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            reader = PdfReader(local_pdf_path)
            num_pages = len(reader.pages)
            pdf_result = {
                "pdf_url": pdf_url,
                "file_name": filename,
                "matches": []
            }

            for page_num in range(num_pages):
                page = reader.pages[page_num]
                text = page.extract_text()
                if text:
                    lines = text.splitlines()
                    for line_index, line in enumerate(lines):
                        for keyword in keywords:
                            # Use regex for case-insensitive whole word search
                            # word_boundaries ensures 'flask' doesn't match 'flasks'
                            pattern = r'\b' + re.escape(keyword) + r'\b'
                            if re.search(pattern, line, re.IGNORECASE):
                                # Capture surrounding context
                                context_start = max(0, line_index - 1)
                                context_end = min(len(lines), line_index + 2)
                                paragraph = " ".join(lines[context_start:context_end]).strip()

                                # Highlight the keyword in the paragraph for display
                                highlighted_paragraph = re.sub(
                                    pattern,
                                    lambda m: f"<strong>{m.group(0)}</strong>", # Use strong for highlighting
                                    paragraph,
                                    flags=re.IGNORECASE
                                )

                                pdf_result["matches"].append({
                                    "keyword": keyword,
                                    "paragraph": paragraph, # Original paragraph for search
                                    "highlighted_paragraph": highlighted_paragraph, # Highlighted for display
                                    "page_number": page_num + 1 # Page numbers are 1-indexed
                                })
                                # Break after first match in line to avoid duplicate paragraph entries for multiple keywords
                                break
            if pdf_result["matches"]:
                search_results.append(pdf_result)

        except requests.exceptions.RequestException as e:
            print(f"Error downloading or processing {pdf_url}: {e}")
            # Optionally, store error message in results
            search_results.append({"pdf_url": pdf_url, "error": str(e)})
        except Exception as e:
            print(f"An unexpected error occurred for {pdf_url}: {e}")
            search_results.append({"pdf_url": pdf_url, "error": f"Processing error: {e}"})

    # Save results to JSON file
    with open(app.config['SEARCH_RESULTS_FILE'], 'w', encoding='utf-8') as f:
        json.dump(search_results, f, ensure_ascii=False, indent=4)

    # Redirect to the results page
    return jsonify({"status": "success", "message": "PDFs processed.", "redirect_url": url_for('show_results')})


@app.route('/results')
def show_results():
    # Load results from the global variable (or file if needed for persistence)
    global search_results
    return render_template('search_results.html', results=search_results)

# @app.route('/viewer')
# def viewer():
#     pdf_url = request.args.get('pdf_url')
#     page = request.args.get('page')
#     keyword = request.args.get('keyword') # Pass the keyword for highlighting
#     return render_template('viewer.html', pdf_url=pdf_url, page=page, keyword=keyword)

# Add this new route in app.py
@app.route('/proxy_pdf/<path:pdf_path>')
def proxy_pdf(pdf_path):
    # Decode the URL that was encoded by the client
    full_pdf_url = request.args.get('url') # Get the original full URL from a query parameter
    if not full_pdf_url:
        return "PDF URL not provided.", 400

    try:
        print(f"Proxying PDF: {full_pdf_url}")
        response = requests.get(full_pdf_url, stream=True, timeout=30) # Increased timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

        # Determine content type (usually 'application/pdf')
        content_type = response.headers.get('Content-Type', 'application/pdf')

        # Create a Flask response that streams the content
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                yield chunk

        # Set headers for PDF display
        headers = {
            'Content-Type': content_type,
            'Content-Disposition': 'inline; filename="proxied_document.pdf"' # Suggest a filename
        }
        return app.response_class(generate(), headers=headers)

    except requests.exceptions.RequestException as e:
        print(f"Error proxying PDF {full_pdf_url}: {e}")
        return f"Error fetching PDF: {e}", 500
    except Exception as e:
        print(f"An unexpected error occurred during proxying: {e}")
        return f"An unexpected error occurred: {e}", 500

# ... (in your viewer route, pass the proxied URL)
@app.route('/viewer')
def viewer():
    original_pdf_url = request.args.get('pdf_url')
    page = request.args.get('page')
    keyword = request.args.get('keyword')

    # Encode the original PDF URL to be safely passed as a query parameter
    # to the proxy_pdf route
    proxied_pdf_url = url_for('proxy_pdf', url=original_pdf_url, _external=True)

    return render_template('viewer.html', pdf_url=proxied_pdf_url, page=page, keyword=keyword)
if __name__ == '__main__':
    app.run(debug=True)