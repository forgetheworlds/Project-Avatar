#!/usr/bin/env python3
"""Standalone arxiv fetcher — no curl pipes, no shell dependencies.
Downloads XML via urllib, parses with stdlib, outputs clean text.

Usage:
  python3 fetch_arxiv.py "search query" [--max N] [--sort date|relevance]
  python3 fetch_arxiv.py --id "2402.03300"
  python3 fetch_arxiv.py --id "2402.03300,2401.12345"  (multiple)
  python3 fetch_arxiv.py --json "search query"

Saves results to splash sources dir if SAVE_DIR env var set.
"""
import sys, os, time, json, re
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET

NS = {'a': 'http://www.w3.org/2005/Atom'}
BASE_URL = "https://export.arxiv.org/api/query"

def _fetch(url):
    """Fetch URL with retry and backoff."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'SplashResearch/1.0 (SplashWaterGunDrone; research@projectavatar.dev)'
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 5 * (attempt + 1)
                print(f"  Rate limited (429). Waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise

def search(query, max_results=5, sort_by='submittedDate'):
    """Search arXiv papers."""
    params = {
        'search_query': f'all:{query}',
        'max_results': str(max_results),
        'sortBy': sort_by,
        'sortOrder': 'descending'
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    print(f"  Searching arxiv...", file=sys.stderr)
    
    xml_data = _fetch(url)
    root = ET.fromstring(xml_data)
    
    papers = []
    for entry in root.findall('a:entry', NS):
        title = entry.find('a:title', NS).text.strip().replace('\n', ' ')
        arxiv_id = entry.find('a:id', NS).text.strip().split('/abs/')[-1]
        published = entry.find('a:published', NS).text[:10]
        updated = entry.find('a:updated', NS).text[:10]
        summary = entry.find('a:summary', NS).text.strip()[:300]
        authors = ', '.join(a.find('a:name', NS).text for a in entry.findall('a:author', NS))
        cats = ', '.join(c.get('term') for c in entry.findall('a:category', NS))
        
        papers.append({
            'id': arxiv_id,
            'title': title,
            'authors': authors,
            'published': published,
            'updated': updated,
            'categories': cats,
            'summary': summary,
            'pdf': f"https://arxiv.org/pdf/{arxiv_id}",
            'abstract_url': f"https://arxiv.org/abs/{arxiv_id}"
        })
    
    return papers

def fetch_by_ids(id_list):
    """Fetch specific papers by ID."""
    ids = ','.join(id_list)
    url = f"{BASE_URL}?id_list={ids}"
    print(f"  Fetching {len(id_list)} paper(s) from arxiv...", file=sys.stderr)
    
    xml_data = _fetch(url)
    root = ET.fromstring(xml_data)
    
    papers = []
    for entry in root.findall('a:entry', NS):
        title = entry.find('a:title', NS).text.strip().replace('\n', ' ')
        arxiv_id = entry.find('a:id', NS).text.strip().split('/abs/')[-1]
        published = entry.find('a:published', NS).text[:10]
        updated = entry.find('a:updated', NS).text[:10]
        summary_val = entry.find('a:summary', NS).text.strip()[:500]
        authors = ', '.join(a.find('a:name', NS).text for a in entry.findall('a:author', NS))
        cats = ', '.join(c.get('term') for c in entry.findall('a:category', NS))
        
        papers.append({
            'id': arxiv_id,
            'title': title,
            'authors': authors,
            'published': published,
            'updated': updated,
            'categories': cats,
            'summary': summary_val,
            'pdf': f"https://arxiv.org/pdf/{arxiv_id}",
            'abstract_url': f"https://arxiv.org/abs/{arxiv_id}"
        })
    
    return papers

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Fetch papers from arXiv')
    parser.add_argument('query', nargs='?', help='Search query')
    parser.add_argument('--max', type=int, default=5, help='Max results')
    parser.add_argument('--sort', choices=['date', 'relevance'], default='date')
    parser.add_argument('--id', help='Fetch specific paper(s) by ID (comma-separated)')
    parser.add_argument('--json', action='store_true', help='JSON output')
    args = parser.parse_args()
    
    if args.id:
        papers = fetch_by_ids([i.strip() for i in args.id.split(',')])
    elif args.query:
        sort_by = 'submittedDate' if args.sort == 'date' else 'relevance'
        papers = search(args.query, args.max, sort_by)
    else:
        parser.print_help()
        sys.exit(1)
    
    if args.json:
        print(json.dumps(papers, indent=2))
    else:
        for i, p in enumerate(papers):
            print(f"\n{'='*70}")
            print(f"Paper {i+1}: [{p['id']}]")
            print(f"  Title: {p['title']}")
            print(f"  Authors: {p['authors']}")
            print(f"  Published: {p['published']} | Categories: {p['categories']}")
            print(f"  Abstract: {p['summary']}...")
            print(f"  PDF: {p['pdf']}")
        print(f"\n{'='*70}")
        print(f"Total: {len(papers)} papers")
    
    # Save to file if SAVE_DIR env var set
    save_dir = os.environ.get('SAVE_DIR')
    if save_dir and papers:
        os.makedirs(save_dir, exist_ok=True)
        safe_query = re.sub(r'[^\w\s-]', '', (args.query or args.id or 'papers'))
        safe_query = re.sub(r'[-\s]+', '_', safe_query.strip())[:50]
        fname = f"arxiv_{safe_query}_{papers[0]['published']}.json"
        fpath = os.path.join(save_dir, fname)
        with open(fpath, 'w') as f:
            json.dump(papers, f, indent=2)
        print(f"\nSaved: {fpath}", file=sys.stderr)
