import re
import lxml
from urllib.parse import urlparse
from urllib.parse import urldefrag

valid_domains = "ics.uci.edu|cs.uci.edu|informatics.uci.edu|stat.uci.edu"


def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [urldefrag(link)[0] for link in links if is_valid(link)]


def extract_next_links(url, resp):
    # Implementation required.
    return list()


def is_valid(url):
    try:
        parsed = urlparse(url)
        # Check if valid http/https link
        if parsed.scheme not in set(["http", "https"]):
            return False
        # Check if not a web page
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False
        # Check if a valid domain
        return re.search(rf"({valid_domains})", parsed.netloc)
    except TypeError:
        print("TypeError for ", parsed)
        raise