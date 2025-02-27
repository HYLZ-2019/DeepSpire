import os
import cloudscraper  # pip install cloudscraper
import tqdm

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "Referer": "https://sts.huijiwiki.com/",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0"
}

SAVE_DIR = "wiki_raw"
os.makedirs(SAVE_DIR, exist_ok=True)

if __name__ == "__main__":
    # Create a scraper that can bypass Cloudflare
    scraper = cloudscraper.create_scraper(browser='chrome')
    scraper.headers.update(HEADERS)
    
    # First visit the main page to get cookies
    print("Visiting main page...")
    main_response = scraper.get("https://sts.huijiwiki.com/", timeout=30)
    print(f"Main page status: {main_response.status_code}")
    
    # Now make the API request with pagination (500 items per request)
    print("Making API requests (500 items per batch)...")
    all_pages = []
    continue_params = {}
    
    while True:
        url = "https://sts.huijiwiki.com/api.php?action=query&list=allpages&apnamespace=0&aplimit=500&format=json"
        
        # Add continue parameters if we have them
        if continue_params:
            for key, value in continue_params.items():
                url += f"&{key}={value}"
        
        response = scraper.get(url, timeout=30)
        print(f"API Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: {response.text[:500]}")
            break
        
        data = response.json()
        
        # Add the pages to our collection
        if "query" in data and "allpages" in data["query"]:
            all_pages.extend(data["query"]["allpages"])
            print(f"Retrieved {len(data['query']['allpages'])} pages (total: {len(all_pages)})")
        
        # Check if we need to continue
        if "continue" in data:
            continue_params = data["continue"]
        else:
            break
    
    # Create a structure similar to the original response for compatibility
    data = {"query": {"allpages": all_pages}}
    if response.status_code == 200:
        import json
        try:
            data = response.json()
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            print("Response was not valid JSON. Response text:")
            print(response.text[:500])
    else:
        print(f"Error: {response.text[:500]}")

    '''
    Output:
    {
        "batchcomplete": "",
        "continue": {
            "apcontinue": "\u6606\u866b\u6807\u672c",
            "continue": "-||"
        },
        "warnings": {
            "allpages": {
            "*": "The value \"2000\" for parameter \"aplimit\" must be between 1 and 500."
            }
        },
        "query": {
            "allpages": [
            {
                "pageid": 6419,
                "ns": 0,
                "title": "BOSS"
            },
    ......

    For each pageid, query the page content with https://sts.huijiwiki.com/api.php?action=parse&amp;pageid=2688&amp;format=json and save to wiki/{pageid}.json
    '''

    for page in data["query"]["allpages"]:
        pageid = page["pageid"]
        print(f"Downloading page {pageid}...")
        page_response = scraper.get(
            f"https://sts.huijiwiki.com/api.php?action=parse&pageid={pageid}&format=json",
            timeout=30
        )
        if page_response.status_code == 200:
            with open(os.path.join(SAVE_DIR, f"{pageid}.html"), "w", encoding="UTF-8") as f:
                # Parse with json, then dump with indent=2
                text = page_response.json()["parse"]["text"]["*"]
                f.write(text)
        else:
            print(f"Error downloading page {pageid}: {page_response.text[:500]}")
    
