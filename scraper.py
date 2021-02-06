import re
import pickle
import json
# Import lxml library for html page analysis
from lxml import html
from lxml.etree import ParseError, ParserError
from lxml.html.clean import Cleaner
from urllib.parse import urlparse
from urllib.parse import urlunparse
import datetime
import os
# Import nltk library for tokenizing
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
# Import datasketch for minhash calculation and index
from datasketch import MinHash, LeanMinHash, MinHashLSH

# you may need to download nltk data in order to make use of the nltk functionality
nltk.download('stopwords')

# whether the data has been initialized
initialized = False
# after how many links to output data
out_cycle = 10
# current link count
out_current = 0
# domains that are valid to crawl
valid_domains = "ics.uci.edu|cs.uci.edu|informatics.uci.edu|stat.uci.edu|today.uci.edu/department" \
                "/information_computer_sciences"
# invalid file types which should be skipped
invalid_types = "css|js|bmp|gif|jpe?g|ico" \
                "|png|tiff?|mid|mp2|mp3|mp4" \
                "|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf" \
                "|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names" \
                "|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso" \
                "|epub|dll|cnf|tgz|sha1|php" \
                "|thmx|mso|arff|rtf|jar|csv|xml|svg" \
                "|rm|smil|wmv|swf|wma|zip|rar|gz"
# invalid paths, these paths have often been found to be useless
invalid_paths = "calender|wp-json"
# enable logging
logging = True
# output file
output = None
# data file name
data_path = "data.json"
# tokens file name
token_path = "tokens.pickle"
# subdomain file name
subdomain_path = "domains.pickle"
# hashes file name
hash_path = "hashes.pickle"
# separator string
separator = "#" * 10 + "\n"
# min text size of a page to analyze
min_size = 1e3
# max size of a page to analyze
max_size = 2e5
# min portion(%) of a page that should be text
min_part = 0.1
# used to get list of tokens in a page, commented out for now
# tokenFile = None
# dict mapping all tokens to total frequency 
word_dict = {}
# List of pages with largest token count
pages_max = []
max_len = -1
# dictionary of subdomains found
subdomain_dic = {}
# sorted list of sub-domains
sorted_domains = []
# unique page count
unique_count = 0
# minhash index
lsh = MinHashLSH(threshold=0.75, num_perm=128)


def scraper(url, resp):
    # check if initialized
    # this is used to load data if not --restart
    global initialized
    if not initialized:
        init()
        initialized = True
    # check out_counter
    # output written data ever set amount of cycles
    global out_current
    if out_current == out_cycle:
        write_data()
        out_current = 0
    else:
        out_current += 1
    # extract links from given url
    links = extract_next_links(url, resp)
    # check if any links were returned
    if not links:
        return list()
    urls = []
    p_url = urlparse(url)
    # check if each link is valid
    # modifies some links to make them valid
    for link in links:
        # parse the url
        parsed = urlparse(link)
        # set scheme if not one
        scheme = parsed.scheme
        if scheme == "":
            scheme = p_url.scheme
        # set netloc if not one
        netloc = parsed.netloc
        if netloc == "":
            netloc = p_url.netloc
        # reconstruct url
        link = urlunparse((scheme, netloc, parsed.path, None, None, None))
        # check if the link is valid
        if is_valid(link):
            # append the url with fragment removed
            urls.append(link)
    return urls


def extract_next_links(url, resp):
    if resp.status == 200:
        # get total size of page
        page_size = len(resp.raw_response.content)
        # check to see if page is to large, if so skip it
        if page_size > max_size:
            return []
        # convert content into html data
        parser = html.HTMLParser(remove_blank_text=True)
        try:
            data = html.document_fromstring(resp.raw_response.content, parser)
            # clean the document
            cleaner = Cleaner(style=True)
            cleaned = cleaner.clean_html(data)
            text = cleaned.text_content()
        except (ParseError, ParserError, UnicodeDecodeError):
            return list()
        text_size = len(text)
        # log the link
        log(f"{resp.status} - {url} - {text_size}/{page_size}\n")
        # check if enough text content exists on page
        # if not skip analysis of this page
        if text_size < min_size or text_size / page_size < min_part:
            return []
        # tokenize the text on the page
        tk, lmh = tokenize_words(url, text)
        # check if similar pages exist
        global lsh
        sim = lsh.query(lmh)
        # if similar pages exist above threshold
        if sim:
            return list()
        lsh.insert(url, lmh)
        # check if page length(token count) and compare with other pages
        page_length(url, len(tk))
        # update the total frequencies of all words from all crawled pages
        word_frequencies(tk)
        # update unique count
        global unique_count
        unique_count += 1
        # check sub-domain of the the url
        p_url = urlparse(url)
        calculate_subdomain(p_url, '.ics.uci.edu')
        # write_data()
        # return all the links in the page
        return [link for element, attribute, link, pos in data.iterlinks()]
    else:
        log(f"{resp.status} - {url} - {resp.error}\n")
    return list()


def is_valid(url):
    try:
        parsed = urlparse(url)
        # Check if valid http/https link
        if parsed.scheme not in set(["http", "https"]):
            return False
        # Check if a valid domain
        if not re.search(rf"({valid_domains})", parsed.netloc):
            return False
        path = parsed.path.lower()
        # Check if not a web page
        if re.match(rf".*\.({invalid_types})", path):
            return False
        # check if path contains file type or invalid characters
        for part in path.split("/"):
            if part.strip() == "":
                continue
            # check if invalid characters are in path
            if re.search(r"^[^a-zA-Z0-9_\-.~]", part):
                return False
            # check if at least one alphanumeric character
            if not re.search(r"[a-zA-Z0-9]", part):
                return False
            # check if the path contains a file type that is invalid
            if re.match(rf"^({invalid_types})$", part):
                return False
            # skip links that we found have little information or lead to traps/loops
            elif re.match(rf"^({invalid_paths})$", part):
                return False
        return True
    except TypeError:
        print("TypeError for ", parsed)
        raise


# outputs message to a log file
def log(message):
    # if logging disabled, do not output anything
    if not logging:
        return
    global output
    # open log file if not already open
    if not output:
        # ensure data folder exists
        if not os.path.isdir('data'):
            os.mkdir('data')
            # open log file
        output = open(f"data/{datetime.datetime.now()}.txt", "w")
    # write message to file
    output.write(message)
    # flush file to save output
    output.flush()

    
# uses nltk word_tokenizer to tokenize the text from a url, returns a list of tokens
def tokenize_words(url, text):
    # preprocessing step, converts all characters to lowercase
    words = text.replace("  ", " ").replace("\n", " ").lower().strip()
    # the tokenizing step
    tokens = word_tokenize(words)
    # this is the list of valid tokens
    ftokens = []
    mh = MinHash(num_perm=128)
    # iterates through full token list to filter out invalid tokens
    for t in tokens:
        # do not include the token if it is a stopword
        if t in stopwords.words():
            continue
        # do not include the token if there are no alphanumeric characters
        if not re.match('[A-Za-z0-9]+', t):
            continue
        # remove any non-alphanumeric characters from the token
        t2 = re.sub('[^A-Za-z0-9]+', '', t).strip()
        # skip the token if it is an empty string
        if len(t2) <= 0:
            continue
        ftokens.append(t2)
        mh.update(t2.encode("utf8"))
    return ftokens, LeanMinHash(mh)


# evaluates the page length of a url (# of valid tokens), updates to a dictionary that tracks page lengths for all urls
# also returns the page length
def page_length(url, length):
    global max_len
    if length < max_len:
        return
    global pages_max
    if length == max_len:
        pages_max.append(url)
    else:
        pages_max = [url]
        max_len = length


# updates word frequency dict with words from current page    
def word_frequencies(ftokens):
    # call wordFreq dict
    global word_dict
    # creates dict if it does not exist yet, creates folder for word_data if it does not exist yet
    # update wordFreq dict, iterates through each token in token list
    for t in ftokens:
        if t not in word_dict:
            word_dict[t] = 0
        word_dict[t] += 1


# calculate the subdomains For Question4
def calculate_subdomain(parsed, suffix):
    current_page_domain = parsed.netloc
    global subdomain_dic
    if current_page_domain.endswith(suffix) and not current_page_domain.endswith('www.ics.uci.edu'):
        if current_page_domain in subdomain_dic:
            subdomain_dic[current_page_domain] += 1
        else:
            subdomain_dic[current_page_domain] = 1


# writes all data needed for continuing after program stopped
# writes all data needed for questions 1-4 into single file
def write_data():
    print("Writing data...")
    # write backup data
    with open(token_path, "wb") as token_file:
        pickle.dump(word_dict, token_file, protocol=pickle.HIGHEST_PROTOCOL)
    with open(subdomain_path, "wb") as domain_file:
        pickle.dump(subdomain_dic, domain_file, protocol=pickle.HIGHEST_PROTOCOL)
    with open(hash_path, "wb") as hash_file:
        pickle.dump(lsh, hash_file, protocol=pickle.HIGHEST_PROTOCOL)
    # write report data
    data = {"unique": unique_count, "longest": max_len, "longest_pages": pages_max,
            "common_words": sorted(word_dict.items(), key=lambda item: item[1], reverse=True)[:50],
            "subdomains": sorted(subdomain_dic.items(), key=lambda item: item[0].lower())}
    with open(data_path, "w") as data_file:
        json.dump(data,data_file, indent=4)
    print("Data written.")


# initializes data using existing data sets
def init():
    # get unique page count and longest page(s)
    if os.path.exists(data_path):
        with open(data_path, "r") as data_file:
            global unique_count
            global max_len
            global pages_max
            data = json.load(data_file)
            unique_count = int(data["unique"])
            max_len = int(data["longest"])
            pages_max = data["longest_pages"]
    # get token counts
    if os.path.exists(token_path):
        with open(token_path, "rb") as token_file:
            global word_dict
            word_dict = pickle.load(token_file)
    # get sub-domain counts
    if os.path.exists(subdomain_path):
        with open(subdomain_path, "rb") as domain_file:
            global subdomain_dic
            subdomain_dic = pickle.load(domain_file)
    # get minhash data
    if os.path.exists(hash_path):
        with open(hash_path, "rb") as hash_file:
            global lsh
            lsh = pickle.load(hash_file)
    print("Data initialized")
